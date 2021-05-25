#!/usr/bin/env python

import os
import json
import itertools
import collections
import bisect
import logging

import redis
import networkx as nx

from cartprograph import context, Node


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
logging.getLogger().setLevel(os.getenv("LOGLEVEL", "INFO"))

redis_client = redis.Redis(host="localhost", port=6379)
context["redis_client"] = redis_client
context["cached_graph"] = nx.DiGraph()
new_id = itertools.count()


def event_node(node):
    l.info(f"Node new or update: {node.id}")
    redis_client.publish(f"event.node", node.id)


def work_trace(node):
    tracepoints = []
    basic_blocks = []
    syscalls = []
    interactions = []
    datapoints = []
    root = True
    node_ids = reversed(
        [
            node.id,
            *(e[1] for e in nx.dfs_edges(context["cached_graph"].reverse(), node.id)),
        ]
    )
    for current_node_id in node_ids:
        current_node = Node(current_node_id)
        if root:
            tracepoints.extend(current_node.tracepoints)
            root = False
        basic_blocks.extend(current_node.basic_blocks)
        syscalls.extend(current_node.syscalls)
        interactions.extend(current_node.interactions)
        datapoints.extend(current_node.datapoints)

    trace = json.dumps(
        {
            "node_id": node.id,
            "tracepoints": tracepoints,
            "basic_blocks": basic_blocks,
            "syscalls": syscalls,
            "interactions": interactions,
            "datapoints": datapoints,
        }
    )
    redis_client.rpush("work.trace", trace)


def initialize_graph(tracepoints=None):
    if tracepoints is None:
        tracepoints = []
    node = Node(next(new_id))
    node.parent_id = None
    node.tracepoints = tracepoints
    node.basic_blocks = []
    node.syscalls = []
    node.interactions = []
    node.datapoints = []
    node.maps = None
    work_trace(node)


def handle_initialize_event(event):
    event_data = json.loads(event["data"])
    tracepoints = event_data["tracepoints"]
    initialize_graph(tracepoints)


def handle_input_event(event):
    event_data = json.loads(event["data"])
    node = Node(event_data["id"])

    input_data = event_data["data"]

    new_node = Node(next(new_id), copy_from=node)

    new_node.interactions[-1]["data"] = input_data
    new_node.invalidate("interactions")

    l.info("New input: %d", new_node.id)

    event_node(new_node)
    work_trace(new_node)


def handle_trace_event(event):
    trace = json.loads(event["data"])
    blocked = event["channel"] == b"event.trace.blocked"

    node_id = trace["node_id"]
    basic_blocks = trace["basic_blocks"]
    syscalls = trace["syscalls"]
    interactions = trace["interactions"]
    datapoints = trace["datapoints"]
    maps = trace["maps"]
    trace_index = 0

    node = Node(node_id)

    if node.parent_id is not None:
        for current_node_id in reversed(
            [e[1] for e in nx.dfs_edges(context["cached_graph"].reverse(), node.id)]
        ):
            current_node = Node(current_node_id)
            basic_blocks = basic_blocks[len(current_node.basic_blocks) :]
            syscalls = syscalls[len(current_node.syscalls) :]
            interactions = interactions[len(current_node.interactions) :]
            datapoints = datapoints[len(current_node.datapoints) :]
            trace_index += len(current_node.basic_blocks)
    else:
        node.maps = maps

    if blocked:
        blocked_basic_block, basic_blocks = basic_blocks[-1], basic_blocks[:-1]
        blocked_syscall, syscalls = syscalls[-1], syscalls[:-1]
        blocked_interaction, interactions = interactions[-1], interactions[:-1]
        blocked_trace_index = blocked_interaction["trace_index"]
        if datapoints and datapoints[-1]["trace_index"] == blocked_trace_index:
            blocked_datapoint, datapoints = datapoints[-1], datapoints[:-1]
        else:
            blocked_datapoint = None

    def iter_interaction_clusters(interactions):
        cluster_attributes = ["channel", "direction"]
        prev_interaction = {"channel": None, "direction": None}
        cluster = []
        for interaction in interactions:
            if (
                any(
                    prev_interaction[attribute] != interaction[attribute]
                    for attribute in cluster_attributes
                )
                and cluster
            ):
                yield cluster
                cluster = []
            cluster.append(interaction)
            prev_interaction = interaction
        if cluster:
            yield cluster

    def iter_cluster_trace_indexes(interaction_clusters):
        clusters = list(interaction_clusters)
        for cluster in [*clusters[1:], None]:
            yield cluster[0]["trace_index"] if cluster else None

    def split_trace(trace, trace_index):
        if trace_index is None:
            return trace[:], []
        split_index = bisect.bisect_left([e["trace_index"] for e in trace], trace_index)
        return trace[:split_index], trace[split_index:]

    clusters = iter_interaction_clusters(interactions)
    current_node = node
    first = True
    for cluster_trace_index in iter_cluster_trace_indexes(clusters):
        if first:
            first = False
        else:
            new_node = Node(next(new_id))
            new_node.parent_id = current_node.id
            current_node = new_node
        delta_index = (
            cluster_trace_index - trace_index
            if cluster_trace_index is not None
            else None
        )
        current_node.basic_blocks = basic_blocks[:delta_index]
        basic_blocks = basic_blocks[delta_index:]
        trace_index = cluster_trace_index
        current_node.syscalls, syscalls = split_trace(syscalls, cluster_trace_index)
        current_node.interactions, interactions = split_trace(
            interactions, cluster_trace_index
        )
        current_node.datapoints, datapoints = split_trace(
            datapoints, cluster_trace_index
        )
        event_node(current_node)

    if blocked:
        new_node = Node(next(new_id))
        new_node.parent_id = current_node.id
        new_node.basic_blocks = [blocked_basic_block]
        new_node.syscalls = [blocked_syscall]
        new_node.interactions = [blocked_interaction]
        new_node.datapoints = [blocked_datapoint] if blocked_datapoint else []
        event_node(new_node)


def main():
    p = redis_client.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(
        **{
            "event.initialize": handle_initialize_event,
            "event.input": handle_input_event,
            "event.trace.blocked": handle_trace_event,
            "event.trace.finished": handle_trace_event,
            # "event.trace.desync": handle_trace_error_event,
            # "event.trace.timeout": handle_trace_error_event,
            # "event.trace.error": handle_trace_error_event,
        }
    )

    initialize_graph()

    for event in p.listen():
        pass


if __name__ == "__main__":
    main()
