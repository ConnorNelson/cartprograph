#!/usr/bin/env python

import string
import random

from flask import Flask, render_template
from flask_socketio import SocketIO, emit


app = Flask(__name__)
socketio = SocketIO(app)


def random_id():
    return int(''.join(random.choice(string.digits) for _ in range(16)))


class Node:
    nodes = {}

    def __init__(self, parent, *, id_=None, text=''):
        self.parent = parent
        self.parentEdge = Edge(parent, self) if parent else None
        self.children = []

        self.id_ = random_id() if id_ is None else id_
        self.text = text

        if self.parent:
            self.parent.children.append(self)

        self.nodes[self.id_] = self

Node.root = Node(None, id_=0)


class Edge:
    edges = {}

    def __init__(self, node1, node2, *, text=''):
        self.node1 = node1
        self.node2 = node2

        self.id_ = random_id()
        self.text = text

        self.edges[self.id_] = self


@app.route("/")
def index_route():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    def recursive_emit(node):
        emit('new_node', {
            'parent': node.parent.id_ if node.parent else None,
            'data': {
                'id': node.id_,
                'text': node.text,
            },
            'edge_data': {
                'id': node.parentEdge.id_,
                'text': node.parentEdge.text,
            } if node.parentEdge else None,
        })
        for child in node.children:
            recursive_emit(child)
    recursive_emit(Node.root)


if __name__ == "__main__":
    node1 = Node(Node.root, text='hello world... 1')
    node2 = Node(Node.root, text='hello world... 2')
    node3 = Node(Node.root, text='hello world... 3')
    node4 = Node(Node.root, text='hello world... 3')

    socketio.run(app, host='0.0.0.0', port=4242)
