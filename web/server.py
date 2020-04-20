#!/usr/bin/env python

import eventlet
eventlet.monkey_patch()

import json

import redis
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room


redis_client = redis.Redis(host='localhost', port=6379)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nothing to hide'
socketio = SocketIO(app, message_queue='redis://localhost:6379/')


@app.route('/<target>')
def index_route(target):
    session['target'] = target
    return render_template('index.html')


@app.route('/api/new_target', methods=['POST'])
def register_target():
    target = request.json['id']
    redis_client.publish(f'{target}.event.create_target', json.dumps({
        'id': request.json['id'],
        'image_name': request.json['image_name'],
        'network': request.json.get('network'),
    }))
    return {'status': 'ok'}


@socketio.on('connect')
def on_connect():
    target = session['target']

    node_ids = sorted([int(n.decode().split('.')[2])
                       for n in redis_client.keys(f'{target}.node.*')])
    for node_id in node_ids:
        node = json.loads(redis_client.get(f'{target}.node.{node_id}'))
        parent_id = node['parent_id']
        if parent_id is not None:
            edge = json.loads(redis_client.get(f'{target}.edge.{parent_id}.{node_id}'))
        else:
            edge = None

        emit('update', {
            'node': node,
            'edge': edge,
        })

    join_room(session['target']);


@socketio.on('input')
def on_input(node):
    target = session['target']
    redis_client.publish(f'{target}.event.input', json.dumps(node))


if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=4242)
