#!/usr/bin/env python

import json
import logging

import redis
from flask_socketio import SocketIO


l = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

redis_client = redis.Redis(host='localhost', port=6379)
socketio = SocketIO(message_queue='redis://localhost:6379')


def handle_node_event(event):
    node_id = int(event['data'])
    node = json.loads(redis_client.get(f'node.{node_id}'))
    parent_id = node['parent_id']
    if parent_id is not None:
        edge = json.loads(redis_client.get(f'edge.{parent_id}.{node_id}'))
    else:
        edge = None

    l.info('Broadcasting %d', node_id)

    socketio.emit('update', {
        'node': node,
        'edge': edge,
    })


def main():
    p = redis_client.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(**{
        'event.node': handle_node_event,
    })

    for event in p.listen():
        pass


if __name__ == '__main__':
    main()
