#!/usr/bin/env python

import os
import re
import time
import signal
import traceback
import pathlib
import json
import contextlib
import logging

import redis
import archr

from tracer import IOBlockingTracer, IO, Block, Desync, on_event, TracerEvent


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
logging.getLogger().setLevel(os.getenv("LOGLEVEL", "INFO"))


TARGET_IMAGE = os.getenv("TARGET_IMAGE")
TARGET_NETWORK = os.getenv("TARGET_NETWORK")
if not TARGET_IMAGE:
    raise Exception("Error: no target image specified")
NAME = os.getenv("SUPERVISOR_PROCESS_NAME")


class timeout(contextlib.ContextDecorator):
    def __init__(self, seconds, suppress_timeout_errors=False):
        self.seconds = int(seconds)
        self.suppress = bool(suppress_timeout_errors)

    def _timeout_handler(self, signum, frame):
        raise TimeoutError()

    def __enter__(self):
        signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(self.seconds)

    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.alarm(0)
        if self.suppress and exc_type is TimeoutError:
            return True


class CartprographTracer(IOBlockingTracer):
    @on_event(TracerEvent.SYSCALL_START, "accept")
    def on_accept(self, syscall, args):
        fd = int(args[0])
        for interaction in self.prev_interactions:
            if interaction["syscall"] == "bind":
                bind_args = interaction["args"]
                bind_fd = int(bind_args[0])
                if bind_fd != fd:
                    continue
                match = re.search(r"sin_port=htons\((?P<port>\d+)\)", bind_args[2])
                if not match:
                    continue
                port = int(match["port"])
                if not port in self.target.tcp_ports:
                    raise Exception(
                        "Target is listening on port %d, but archr is not aware of it",
                        port,
                    )
                l.info("Connecting to port %d", port)
                port_index = self.target.tcp_ports.index(port)
                channel_name = f"tcp:{port_index}"
                self.flight.get_channel(channel_name)
                self.fd_channels[fd] = channel_name
                return

    @on_event(TracerEvent.SYSCALL_FINISH, "accept")
    def on_accept_finished(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            channel = self.fd_channels[fd]
            del self.fd_channels[fd]
            self.fd_channels[result] = channel

    @on_event(TracerEvent.SYSCALL_START, "read")
    def on_read_socket(self, syscall, args):
        fd = int(args[0])
        if fd not in self.fd_channels:
            return
        channel_name = self.fd_channels[fd]
        port_index = int(channel_name.split(":")[1])
        port = self.target.tcp_ports[port_index]
        if "io" not in self.current_interaction:
            self.current_interaction["io"] = IO(f"tcp:{port}", "read", None)
            raise Block(self, syscall, args)
        else:
            io = self.current_interaction["io"]
            channel = self.flight.get_channel(channel_name)
            if io.data:
                l.debug("tcp:%d read: %s", port, io.data)
                channel.write(io.data)
            else:
                l.debug("tcp:%d read: shutdown_wr", port)
                channel.shutdown_wr()

    @on_event(TracerEvent.SYSCALL_FINISH, "write")
    def on_write_socket(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            channel_name = self.fd_channels[fd]
            port_index = int(channel_name.split(":")[1])
            port = self.target.tcp_ports[port_index]
            channel = self.flight.get_channel(channel_name)
            output = channel.read(result)
            l.debug("tcp:%d write: %s", port, output)
            assert len(output) == result
            io = IO(f"tcp:{port}", "write", output)
            if "io" in self.prev_interaction:
                if self.prev_interaction["io"] != io:
                    raise Desync("socket write", self.prev_interaction["io"], io)
            else:
                self.prev_interaction["io"] = io

    @on_event(TracerEvent.SYSCALL_FINISH, "close")
    def on_close(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            del self.fd_channels[fd]

    @on_event(TracerEvent.SYSCALL_FINISH, "dup*")
    def on_dup(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            self.fd_channels[result] = self.fd_channels[fd]


def serialize_interaction(interaction):
    data = [{k: v for k, v in e.items()} for e in interaction]
    for e in data:
        if "io" in e:
            io = e["io"]
            e["io"] = {
                "channel": io.channel,
                "direction": io.direction,
                "data": io.data.decode("latin") if io.data is not None else None,
            }
    return data


def deserialize_interaction(interaction):
    for e in interaction:
        e["args"] = tuple(e["args"])
        if "io" in e:
            io = e["io"]
            io = IO(
                io["channel"],
                io["direction"],
                io["data"].encode("latin") if io["data"] is not None else None,
            )
            e["io"] = io
    return interaction


def main():
    redis_client = redis.Redis(host="localhost", port=6379)

    while True:
        target = archr.targets.DockerImageTarget(TARGET_IMAGE, network=TARGET_NETWORK)
        target.build()
        target.start(name=NAME)
        with target:
            _, trace = redis_client.blpop("work.trace")
            trace = json.loads(trace)

            interaction = deserialize_interaction(trace["interaction"])
            bb_trace = trace["bb_trace"]
            machine = None

            def Machine(argv, *, trace_socket, std_streams):
                nonlocal machine  # TODO: refactor
                machine = CartprographTracer(
                    target.target_args,
                    interaction=interaction,
                    bb_trace=bb_trace,
                    trace_socket=trace_socket,
                    std_streams=std_streams,
                )
                machine.target = target
                machine.fd_channels = {}
                return machine

            def publish_trace(channel):
                trace["interaction"] = serialize_interaction(machine.interaction)
                trace["bb_trace"] = machine.bb_trace
                trace_data = json.dumps(trace)
                redis_client.publish(channel, trace_data)

            l.info("Tracing")
            start_time = time.perf_counter()

            try:
                with timeout(180):
                    analyzer = archr.analyzers.QTraceAnalyzer(target)
                    analyzer.fire(Machine, timeout_exception=False)

            except Block:
                end_time = time.perf_counter()
                total_time = round(end_time - start_time, 3)
                l.info(f"Traced in {total_time}s")

                publish_trace("event.trace.blocked")

            except Desync as e:
                trace["annotation"] = traceback.format_exc()
                publish_trace("event.trace.desync")

            except TimeoutError:
                publish_trace("event.trace.timeout")

            except Exception as e:
                trace["annotation"] = traceback.format_exc()
                publish_trace("event.trace.error")

            else:
                publish_trace("event.trace.finished")


if __name__ == "__main__":
    main()
