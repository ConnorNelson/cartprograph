#!/usr/bin/env python

import json
import random
import string
import logging

import redis
import networkx as nx


l = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

redis_client = redis.Redis(host='localhost', port=6379)
tree = nx.DiGraph()


def handle_input_event(event):
    node_id = int(event['data'])
    node = json.loads(redis_client.get(f'node.{node_id}'))

    l.info('New Input: %d', node_id)

    tree.add_node(node['id'], **node)

    interaction = []
    root = tree.nodes()[0]
    interaction.extend(root['interaction'])
    path = nx.shortest_path(tree, 0, node['id'])
    for n1, n2 in zip(path, path[1:]):
        node1 = tree.nodes()[n1]
        node2 = tree.nodes()[n2]
        edge = tree.edges()[n1, n2]
        interaction.extend(edge['interaction'])
        interaction.extend(node2['interaction'])

    trace = json.dumps({
        'node_id': node_id,
        'interaction': interaction,
    })
    redis_client.rpush('work.trace', trace)

    redis_client.publish('event.node', node_id)


def handle_trace_event(event):
    channel = event['channel'].decode()
    if channel not in ['event.trace.blocked', 'event.trace.finished']:
        return

    blocked = channel == 'event.trace.blocked'

    trace = json.loads(event['data'])
    node_id = trace['node_id']
    interaction = trace['interaction']

    l.info('New Trace: %d', node_id)

    interaction_index = 0
    root = tree.nodes()[0]
    interaction_index += len(root['interaction'])
    path = nx.shortest_path(tree, 0, node_id)
    for n1, n2 in zip(path, path[1:]):
        node1 = tree.nodes()[n1]
        node2 = tree.nodes()[n2]
        edge = tree.edges()[n1, n2]
        interaction_index += len(edge['interaction'])
        if n2 != node_id:
            interaction_index += len(node2['interaction'])
    interaction = interaction[interaction_index:]

    def io_partitioned_interactions():
        current = []
        for e in interaction:
            if 'io' in e or e['syscall'] in ['execve', 'exit', 'exit_group']:
                yield current
                yield [e]
                current = []
            else:
                current.append(e)

    def random_id():
        return int(''.join(random.choice(string.digits) for _ in range(16)))

    partitions = iter(io_partitioned_interactions())

    _ = next(partitions)
    tree.nodes()[node_id]['interaction'] = next(partitions)
    redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
    redis_client.publish('event.node', node_id)

    prev_node_id = node_id
    for edge_partition in partitions:
        node_partition = next(partitions)
        node_id = random_id()
        tree.add_node(node_id, **{
            'id': node_id,
            'parent_id': prev_node_id,
            'interaction': node_partition,
        })
        tree.add_edge(prev_node_id, node_id, **{
            'start_node_id': prev_node_id,
            'end_node_id': node_id,
            'interaction': edge_partition,
        })
        redis_client.set(f'edge.{prev_node_id}.{node_id}',
              json.dumps(tree.edges()[prev_node_id, node_id]))
        redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))
        redis_client.publish('event.node', node_id)
        prev_node_id = node_id


def main():
    p = redis_client.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(**{
        'event.input': handle_input_event,
        'event.trace.*': handle_trace_event,
    })

    nodes = [json.loads(redis_client.get(key)) for key in redis_client.keys('node.*')]
    edges = [json.loads(redis_client.get(key)) for key in redis_client.keys('edge.*')]
    for node in nodes:
        tree.add_node(node['id'], **node)
    for edge in edges:
        tree.add_edge(edge['start_node_id'], edge['end_node_id'], **edge)

    if not nodes:
        node_id = 0
        tree.add_node(0, **{
            'id': node_id,
            'parent_id': None,
            'interaction': [],
        })
        redis_client.set(f'node.{node_id}', json.dumps(tree.nodes()[node_id]))

        trace = json.dumps({
            'node_id': node_id,
            'interaction': [],
        })
        redis_client.rpush('work.trace', trace)

    for event in p.listen():
        pass


if __name__ == '__main__':
    main()
