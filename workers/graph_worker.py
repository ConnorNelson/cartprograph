#!/usr/bin/env python

import os
import json
import itertools
import logging

import redis
import networkx as nx


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))

redis_client = redis.Redis(host='localhost', port=6379)
tree = nx.DiGraph()
new_id = itertools.count()


def handle_input_event(event):
    node = json.loads(event['data'])
    node_id = node['id']

    prev_node_id = node['parent_id']
    edge = tree.edges()[prev_node_id, node_id]

    node_id = next(new_id)
    node['id'] = node_id

    l.info('New Input: %d', node_id)

    tree.add_node(node_id, **node)
    tree.add_edge(prev_node_id, node_id, **edge)
    redis_client.set(f'edge.{prev_node_id}.{node_id}',
                     json.dumps(tree.edges()[prev_node_id, node_id]))
    redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
    redis_client.publish('event.node', node_id)

    interaction = []
    bb_trace = []
    root = tree.nodes()[0]
    interaction.extend(root['interaction'])
    bb_trace.extend(root['bb_trace'])
    path = nx.shortest_path(tree, 0, node['id'])
    for n1, n2 in zip(path, path[1:]):
        node1 = tree.nodes()[n1]
        node2 = tree.nodes()[n2]
        edge = tree.edges()[n1, n2]
        interaction.extend(edge['interaction'])
        interaction.extend(node2['interaction'])
        bb_trace.extend(edge['bb_trace'])
        bb_trace.extend(node2['bb_trace'])

    trace = json.dumps({
        'node_id': node_id,
        'interaction': interaction,
        'bb_trace': bb_trace,
    })
    redis_client.rpush('work.trace', trace)


def handle_trace_event(event):
    trace = json.loads(event['data'])
    node_id = trace['node_id']
    interaction = trace['interaction']
    bb_trace = trace['bb_trace']

    l.info('New Trace: %d', node_id)
    l.debug('trace: %s', trace)

    interaction_index = 0
    bb_trace_index = 0
    root = tree.nodes()[0]
    interaction_index += len(root['interaction'])
    path = nx.shortest_path(tree, 0, node_id)
    for n1, n2 in zip(path, path[1:]):
        node1 = tree.nodes()[n1]
        node2 = tree.nodes()[n2]
        edge = tree.edges()[n1, n2]
        interaction_index += len(edge['interaction'])
        bb_trace_index += len(edge['bb_trace'])
        if n2 != node_id:
            interaction_index += len(node2['interaction'])
            bb_trace_index += len(node2['bb_trace'])
    interaction = interaction[interaction_index:]

    def io_partitions():
        current = []
        for e in interaction:
            if 'io' in e or e['syscall'] in ['execve', 'exit', 'exit_group']:
                yield current
                yield [e]
                current = []
            else:
                current.append(e)

    def grouped_partitions():
        partitions = iter(io_partitions())
        result = []
        for edge_partition in partitions:
            node_partition = next(partitions)
            if not result:
                result.append((edge_partition, node_partition))
                continue
            prev_edge_partition, prev_node_partition = result[-1]
            current_io = node_partition[0]['io'] if len(node_partition) == 1 and 'io' in node_partition[0] else None
            prev_io = prev_node_partition[-1]['io'] if 'io' in prev_node_partition[-1] else None
            if (current_io and prev_io and not edge_partition and
                current_io['channel'] == prev_io['channel'] and
                current_io['direction'] == prev_io['direction'] and
                current_io['data'] is not None):
                prev_node_partition.extend(node_partition)
            else:
                result.append((edge_partition, node_partition))
        yield from result

    partitions = iter(grouped_partitions())

    _, node_partition = next(partitions)
    node_bb_trace_index = node_partition[-1]['bb_trace_index']
    tree.nodes()[node_id]['interaction'] = node_partition
    tree.nodes()[node_id]['bb_trace'] = bb_trace[bb_trace_index:node_bb_trace_index]
    bb_trace_index = node_bb_trace_index
    redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
    redis_client.publish('event.node', node_id)

    prev_node_id = node_id
    for edge_partition, node_partition in partitions:
        node_id = next(new_id)
        edge_bb_trace_index = (edge_partition[-1]['bb_trace_index']
                               if edge_partition else bb_trace_index)
        tree.add_edge(prev_node_id, node_id, **{
            'start_node_id': prev_node_id,
            'end_node_id': node_id,
            'interaction': edge_partition,
            'bb_trace': bb_trace[bb_trace_index:edge_bb_trace_index]
        })
        bb_trace_index = edge_bb_trace_index
        node_bb_trace_index = node_partition[-1]['bb_trace_index']
        tree.add_node(node_id, **{
            'id': node_id,
            'parent_id': prev_node_id,
            'interaction': node_partition,
            'bb_trace': bb_trace[bb_trace_index:node_bb_trace_index]
        })
        bb_trace_index = node_bb_trace_index
        redis_client.set(f'edge.{prev_node_id}.{node_id}',
              json.dumps(tree.edges()[prev_node_id, node_id]))
        redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
        redis_client.publish('event.node', node_id)
        prev_node_id = node_id


def handle_trace_desync_event(event):
    trace = json.loads(event['data'])
    node_id = trace['node_id']

    tree.nodes()[node_id]['interaction'] = [{
        'syscall': 'error',
        'args': [],
        'io': {
            'channel': 'error',
            'direction': 'desync',
            'data': '',
        }
    }]
    tree.nodes()[node_id]['bb_trace'] = []
    redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
    redis_client.publish('event.node', node_id)


def main():
    p = redis_client.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(**{
        'event.input': handle_input_event,
        'event.trace.blocked': handle_trace_event,
        'event.trace.finished': handle_trace_event,
        'event.trace.desync': handle_trace_desync_event,
    })

    nodes = [json.loads(redis_client.get(key)) for key in redis_client.keys('node.*')]
    edges = [json.loads(redis_client.get(key)) for key in redis_client.keys('edge.*')]
    for node in nodes:
        tree.add_node(node['id'], **node)
    for edge in edges:
        tree.add_edge(edge['start_node_id'], edge['end_node_id'], **edge)

    if not nodes:
        node_id = next(new_id)
        tree.add_node(node_id, **{
            'id': node_id,
            'parent_id': None,
            'interaction': [],
            'bb_trace': [],
        })
        redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))

        trace = json.dumps({
            'node_id': node_id,
            'interaction': [],
            'bb_trace': [],
        })
        redis_client.rpush('work.trace', trace)

    for event in p.listen():
        pass


if __name__ == '__main__':
    main()
