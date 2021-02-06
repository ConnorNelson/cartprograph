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
import qtrace


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


class Block(Exception):
    pass


class Desync(Exception):
    pass


class TracingList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_index = 0
        self.initial_len = len(self)

    @property
    def tracing(self):
        return self.current_index < self.initial_len

    @property
    def current(self):
        return self[self.current_index]

    @property
    def previous(self):
        return self[self.current_index - 1]

    def append(self, element, *, ignore_attrs=None):
        if self.tracing:
            if ignore_attrs:
                attrs = (set(self.current) | set(element)) - set(ignore_attrs)
                if any(self.current[attr] != element[attr] for attr in attrs):
                    raise Desync()
            elif self.current != element:
                raise Desync()
        else:
            super().append(element)
        self.current_index += 1


class CartprographTracer(qtrace.TraceMachine):
    def __init__(
        self,
        target,
        basic_blocks,
        syscalls,
        interactions,
        *,
        trace_socket,
    ):
        super().__init__(argv=target.target_args, trace_socket=trace_socket)

        self.target = target
        self.basic_blocks = TracingList(basic_blocks)
        self.syscalls = TracingList(syscalls)
        self.interactions = TracingList(interactions)

        self.trace_index = -1

    def run(self, *args, **kwargs):
        # TODO: Refactor
        # We have access to .process at this point
        self.fd_channels = {
            0: self.process.stdin,
            1: self.process.stdout,
            2: self.process.stderr,
        }

        syscall = {
            "nr": None,
            "name": "execve",
            "args": [self.target.target_args[0], self.target.target_args, {}],
            "ret": None,
            "trace_index": -1,
        }
        self.syscalls.append(syscall)

        super().run(*args, **kwargs)

    def on_basic_block(self, address):
        super().on_basic_block(address)
        self.basic_blocks.append(address)
        self.trace_index += 1

    def on_syscall_start(self, syscall_nr, *args):
        super().on_syscall_start(syscall_nr, *args)
        syscall_name = qtrace.syscalls["x86_64"][syscall_nr][1][len("sys_") :]
        l.debug(f"Trace syscall start: {syscall_name}")
        syscall = {
            "nr": syscall_nr,
            "name": syscall_name,
            "args": list(args),
            "ret": None,
            "trace_index": self.trace_index,
        }
        self.syscalls.append(syscall, ignore_attrs=["ret"])

        if syscall_name == "read":
            fd = args[0]
            if fd in self.fd_channels:
                count = args[2]
                self.handle_read(fd, count)

    def on_syscall_end(self, syscall_nr, ret):
        super().on_syscall_end(syscall_nr, ret)
        current_syscall = self.syscalls.previous
        syscall_name = current_syscall["name"]
        l.debug(f"Trace syscall end: {syscall_name}")
        assert current_syscall["nr"] == syscall_nr
        assert current_syscall["trace_index"] == self.trace_index
        if self.syscalls.tracing:
            assert current_syscall["ret"] == ret
        current_syscall["ret"] = ret

        if syscall_name == "write":
            args = current_syscall["args"]
            fd = args[0]
            if fd in self.fd_channels:
                count = args[2]
                self.handle_write(fd, count)

    def handle_read(self, fd, count):
        std_channels = {
            0: "stdio",
            1: "stdio",
            2: "stderr",
        }
        interaction = {
            "channel": std_channels[fd],
            "direction": "input",
            "data": None,
            "trace_index": self.trace_index,
        }
        if not self.interactions.tracing:
            self.interactions.append(interaction)
            raise Block()
        else:
            current_interaction = self.interactions.current
            for attr in ["channel", "direction", "trace_index"]:
                if current_interaction[attr] != interaction[attr]:
                    raise Desync()
            channel = self.fd_channels[fd]
            data = current_interaction["data"]
            channel.write(data.encode("latin"))
            channel.flush()
            interaction["data"] = data
            self.interactions.append(interaction)

    def handle_write(self, fd, count):
        std_channels = {
            0: "stdio",
            1: "stdio",
            2: "stderr",
        }
        channel = self.fd_channels[fd]
        data = channel.read(count)
        interaction = {
            "channel": std_channels[fd],
            "direction": "output",
            "data": data.decode("latin"),
            "trace_index": self.trace_index,
        }
        self.interactions.append(interaction)


def main():
    redis_client = redis.Redis(host="localhost", port=6379)

    while True:
        target = archr.targets.DockerImageTarget(TARGET_IMAGE, network=TARGET_NETWORK)
        target.build()
        target.start(name=NAME)
        with target:
            _, trace = redis_client.blpop("work.trace")
            trace = json.loads(trace)

            node_id = trace["node_id"]
            basic_blocks = trace["basic_blocks"]
            syscalls = trace["syscalls"]
            interactions = trace["interactions"]
            machine = None

            def Machine(argv, *, trace_socket, std_streams):
                nonlocal machine  # TODO: refactor
                machine = CartprographTracer(
                    target,
                    basic_blocks,
                    syscalls,
                    interactions,
                    trace_socket=trace_socket,
                )
                return machine

            def publish_trace(channel):
                trace["basic_blocks"] = machine.basic_blocks
                trace["syscalls"] = machine.syscalls
                trace["interactions"] = machine.interactions
                trace_data = json.dumps(trace)
                redis_client.publish(channel, trace_data)
                l.info(f"New trace ({channel}) from node {node_id}")

            l.info(f"Tracing node {node_id}")
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

            # except Desync as e:
            #     trace["annotation"] = traceback.format_exc()
            #     publish_trace("event.trace.desync")

            # except TimeoutError:
            #     publish_trace("event.trace.timeout")

            # except Exception as e:
            #     trace["annotation"] = traceback.format_exc()
            #     publish_trace("event.trace.error")

            else:
                publish_trace("event.trace.finished")


if __name__ == "__main__":
    main()
