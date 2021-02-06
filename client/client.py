import os
import time

import networkx as nx
import requests
import socketio

URL = "http://localhost:4242/"


class GraphUpdateNamespace(socketio.ClientNamespace):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph = nx.DiGraph()

    def on_update(self, data):
        parent_id, node_id = data["src_id"], data["dst_id"]

        def get_trace(attr):
            return requests.get(f"{URL}/trace/{attr}/{node_id}").json()

        node_attrs = {
            attr: get_trace(attr)
            for attr in ["basic_blocks", "syscalls", "interactions"]
        }
        self.graph.add_node(node_id, **node_attrs)
        if node_id:
            self.graph.add_edge(parent_id, node_id)


def pretty_print(color, *values, depth=None, reset=True, end="\n"):
    colors = {
        "black": "\u001b[30m",
        "red": "\u001b[31m",
        "green": "\u001b[32m",
        "yellow": "\u001b[33m",
        "blue": "\u001b[34m",
        "magenta": "\u001b[35m",
        "cyan": "\u001b[36m",
        "white": "\u001b[37m",
        "reset": "\u001b[0m",
    }
    if depth is not None:
        print(colors["yellow"] + "+" + "-" * (2 * depth), end=" ")
    print(colors[color], end="")
    print(*values, end="")
    if reset:
        print(colors["reset"], end=end)


def main():
    client = socketio.Client()
    graph_update_namespace = GraphUpdateNamespace()
    client.register_namespace(graph_update_namespace)
    client.connect(URL)

    graph = graph_update_namespace.graph
    while 0 not in graph.nodes:
        time.sleep(1)

    while True:
        os.system("clear")

        depths = nx.shortest_path_length(graph, 0)

        for node_id in nx.dfs_preorder_nodes(graph, 0):
            node = graph.nodes[node_id]
            depth = depths[node_id]

            syscalls = node["syscalls"]
            interactions = node["interactions"]

            if syscalls[0]["name"] == "execve":
                pretty_print("magenta", syscalls[0]["args"][1], depth=depth)

            elif interactions and interactions[0]["direction"] == "input":
                if interactions[0]["data"] is None:
                    pretty_print("yellow", f"[INTERACT {node_id}]", depth=depth)
                else:
                    data = "".join(interaction["data"] for interaction in interactions)
                    pretty_print("blue", repr(data), depth=depth)

            elif interactions and interactions[0]["direction"] == "output":
                data = "".join(interaction["data"] for interaction in interactions)
                pretty_print("green", repr(data), depth=depth)

            else:
                assert False

        print()

        node_id = input("INTERACT Node ID: ")
        if not node_id:
            continue
        node_id = int(node_id)

        print()

        for ancestor_node_id in nx.shortest_path(graph, 0, node_id):
            if ancestor_node_id in [0, node_id]:
                continue
            node = graph.nodes[ancestor_node_id]

            interactions = node["interactions"]

            if interactions and interactions[0]["direction"] == "input":
                data = "".join(interaction["data"] for interaction in interactions)
                pretty_print("blue", data, end="")
            elif interactions and interactions[0]["direction"] == "output":
                data = "".join(interaction["data"] for interaction in interactions)
                pretty_print("green", data, end="")

        pretty_print("blue", reset=False)

        data = input() + "\n"
        requests.post(f"{URL}/input/{node_id}", json={"input": data})

    client.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
