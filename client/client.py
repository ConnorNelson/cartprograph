import os
import time
import copy

import networkx as nx
import socketio


class GraphUpdateNamespace(socketio.ClientNamespace):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph = nx.DiGraph()

    def on_update(self, data):
        node = data["node"]
        edge = data["edge"]
        self.graph.add_node(node["id"], **node)
        if edge:
            assert node["parent_id"] == edge["start_node_id"]
            # TODO: fix bug assert edge["end_node_id"] == node["id"]
            self.graph.add_edge(node["parent_id"], node["id"], **edge)


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
    client.connect("http://localhost:4242/")

    graph = graph_update_namespace.graph
    while 0 not in graph.nodes:
        time.sleep(1)

    while True:
        os.system("clear")

        depths = nx.shortest_path_length(graph, 0)

        for node in nx.dfs_preorder_nodes(graph):
            depth = depths[node]
            interaction, *coalesced_interaction = graph.nodes[node]["interaction"]

            syscall = interaction["syscall"]

            if syscall == "execve":
                pretty_print("magenta", interaction["args"][1], depth=depth)

            elif syscall == "read":
                io = interaction["io"]
                data = io["data"]
                if data is None:
                    assert not coalesced_interaction
                    pretty_print("yellow", f"[INTERACT {node}]", depth=depth)
                else:
                    data += "".join(e["io"]["data"] for e in coalesced_interaction)
                    pretty_print("blue", repr(data), depth=depth)

            elif syscall == "write":
                io = interaction["io"]
                data = io["data"]
                data += "".join(e["io"]["data"] for e in coalesced_interaction)
                pretty_print("green", repr(data), depth=depth)

            elif "exit" in syscall:
                exit_code = interaction["args"][0]
                pretty_print("magenta", f"[EXIT {exit_code}]", depth=depth)

        print()

        node_id = input("INTERACT Node ID: ")
        if not node_id:
            continue
        node_id = int(node_id)

        print()

        for ancestor_node in nx.shortest_path(graph, 0, node_id):
            if ancestor_node in [0, node_id]:
                continue
            interaction, *coalesced_interaction = graph.nodes[ancestor_node][
                "interaction"
            ]
            syscall = interaction["syscall"]
            io = interaction["io"]
            data = io["data"]
            data += "".join(e["io"]["data"] for e in coalesced_interaction)
            if syscall == "read":
                pretty_print("blue", data, end="")
            elif syscall == "write":
                pretty_print("green", data, end="")

        node = copy.deepcopy(graph.nodes[node_id])
        interaction = node["interaction"][0]
        assert interaction["syscall"] == "read" and interaction["io"]["data"] is None

        pretty_print("blue", reset=False)

        data = input()
        interaction["io"]["data"] = data + "\n"
        client.emit("input", node)

    client.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
