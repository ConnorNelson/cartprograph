#!/usr/bin/env python

import eventlet

eventlet.monkey_patch()

import json

import redis
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from cartprograph import context, Node


redis_client = redis.Redis(host="localhost", port=6379)
context["redis_client"] = redis_client

app = Flask(__name__)
app.config["SECRET_KEY"] = "SECRET"
socketio = SocketIO(app, message_queue="redis://localhost:6379/")


@app.route("/")
def index_route():
    return jsonify({"status": "ok"})


@app.route("/trace/basic_blocks/<node_id>")
def trace_basic_block(node_id):
    return jsonify(Node(node_id).basic_blocks)


@app.route("/trace/syscalls/<node_id>")
def trace_syscall(node_id):
    return jsonify(Node(node_id).syscalls)


@app.route("/trace/interactions/<node_id>")
def trace_interactions(node_id):
    return jsonify(Node(node_id).interactions)


@app.route("/input/<id>", methods=["POST"])
def new_input(id):
    input_ = {
        "id": int(id),
        "data": request.json["input"],
    }
    redis_client.publish("event.input", json.dumps(input_))
    return jsonify(dict(success=True))


@socketio.on("connect")
def on_connect():
    node_ids = sorted(
        [int(n.decode().split(".")[1]) for n in redis_client.keys("node.*")]
    )
    for node_id in node_ids:
        parent_id = Node(node_id).parent_id
        emit(
            "update",
            {
                "src_id": parent_id,
                "dst_id": node_id,
            },
        )


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=4242)
