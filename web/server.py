#!/usr/bin/env python

import eventlet

eventlet.monkey_patch()

import json

import redis
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room


redis_client = redis.Redis(host="localhost", port=6379)
app = Flask(__name__)
app.config["SECRET_KEY"] = "nothing to hide"
socketio = SocketIO(app, message_queue="redis://localhost:6379/")


@app.route("/")
def index_route():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    node_ids = sorted(
        [int(n.decode().split(".")[1]) for n in redis_client.keys("node.*")]
    )
    for node_id in node_ids:
        node = json.loads(redis_client.get(f"node.{node_id}"))
        parent_id = node["parent_id"]
        if parent_id is not None:
            edge = json.loads(redis_client.get(f"edge.{parent_id}.{node_id}"))
        else:
            edge = None

        emit(
            "update",
            {
                "node": node,
                "edge": edge,
            },
        )

    # TODO: does a room need to be joined?
    # join_room(session["target"])


@socketio.on("input")
def on_input(node):
    redis_client.publish("event.input", json.dumps(node))


@socketio.on("annotate")
def on_annotate(node):
    redis_client.publish("event.annotate", json.dumps(node))


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=4242)
