#!/usr/bin/env python

import os
import json
import logging

import redis
from flask_socketio import SocketIO

from cartprograph import context, Node


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
logging.getLogger().setLevel(os.getenv("LOGLEVEL", "INFO"))

redis_client = redis.Redis(host="localhost", port=6379)
socketio = SocketIO(message_queue="redis://localhost:6379")
context["redis_client"] = redis_client


def handle_node_event(event):
    node = Node(int(event["data"]))

    l.info("Broadcasting %d", node.id)

    socketio.emit(
        "update",
        {
            "src_id": node.parent_id,
            "dst_id": node.id,
        },
    )


def main():
    p = redis_client.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(
        **{
            "event.node": handle_node_event,
        }
    )

    for event in p.listen():
        pass


if __name__ == "__main__":
    main()
