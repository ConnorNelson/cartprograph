#!/usr/bin/env python

import eventlet
eventlet.monkey_patch()

import json

import redis
from flask import Flask, render_template
from flask_socketio import SocketIO, emit


redis_client = redis.Redis(host='localhost', port=6379)
app = Flask(__name__)
socketio = SocketIO(app, message_queue='redis://localhost:6379/')


@app.route("/")
def index_route():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    def recursive_emit(node_id):
        node = json.loads(redis_client.get(f'node.{node_id}'))
        parent_id = node['parent_id']
        if parent_id is not None:
            edge = json.loads(redis_client.get(f'edge.{parent_id}.{node_id}'))
        else:
            edge = None

        emit('update', {
            'node': node,
            'edge': edge,
        })

        children_edges = redis_client.keys(f'edge.{node_id}.*')
        for child_edge in children_edges:
            _, _, child_id = child_edge.decode().split('.')
            child_id = int(child_id)
            recursive_emit(child_id)

    recursive_emit(0)


@socketio.on('input')
def on_input(node):
    node_id = node['id']
    redis_client.set(f'node.{node_id}', json.dumps(node))
    redis_client.publish('event.input', node_id)


if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=4242)
