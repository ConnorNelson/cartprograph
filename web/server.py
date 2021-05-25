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
app.config["JSON_SORT_KEYS"] = False
socketio = SocketIO(app, message_queue="redis://localhost:6379/")


def all_nodes():
    node_ids = sorted(
        set(int(n.decode().split(".")[1]) for n in redis_client.keys("node.*"))
    )
    for node_id in node_ids:
        yield Node(node_id)


@app.route("/")
def index_route():
    return jsonify(dict(status="alive"))


@app.route("/initialize", methods=["POST"])
def initialize():
    tracepoints = request.json["tracepoints"]
    initialize = {
        "tracepoints": tracepoints,
    }
    redis_client.publish("event.initialize", json.dumps(initialize))
    return jsonify(dict(success=True))


@app.route("/nodes")
def nodes():
    return jsonify(dict(nodes=[node.id for node in all_nodes()]))


@app.route("/trace/basic_blocks/<node_id>")
def trace_basic_block(node_id):
    return jsonify(Node(node_id).basic_blocks)


@app.route("/trace/syscalls/<node_id>")
def trace_syscall(node_id):
    return jsonify(Node(node_id).syscalls)


@app.route("/trace/interactions/<node_id>")
def trace_interactions(node_id):
    return jsonify(Node(node_id).interactions)


@app.route("/trace/datapoints/<node_id>")
def trace_datapoints(node_id):
    return jsonify(Node(node_id).datapoints)


@app.route("/trace/maps")
def trace_maps():
    return jsonify(Node(0).maps)


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
    for node in all_nodes():
        emit(
            "update",
            {
                "src_id": node.parent_id,
                "dst_id": node.id,
            },
        )


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=4242)
