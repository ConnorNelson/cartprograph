import os
import logging

from .tracer import TracerEvent, on_event
from .interaction_tracer import InteractionTracer, Desync


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))


class IO:
    def __init__(self, channel, direction, data):
        self.channel = channel
        self.direction = direction
        self.data = data
        self.excess_data = b""

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.channel == other.channel
            and self.direction == other.direction
            and self.data == other.data
        )

    def __repr__(self):
        return (
            f"<IO channel={self.channel} direction={self.direction} data={self.data}>"
        )


class Block(Exception):
    def __init__(self, machine, syscall, args, result=None):
        self.machine = machine
        self.syscall = syscall
        self.args = args
        self.result = result


class IOBlockingTracer(InteractionTracer):
    def __init__(
        self,
        argv,
        handle_block=None,
        *,
        interaction=None,
        bb_trace=None,
        trace_socket=None,
        std_streams=(None, None, None),
    ):
        super().__init__(
            argv,
            interaction=interaction,
            bb_trace=bb_trace,
            trace_socket=trace_socket,
            std_streams=std_streams,
        )
        self.handle_block = handle_block

    def run(self):
        prev_block = None
        while True:
            try:
                super().run()
            except Block as e:
                if prev_block is False:
                    break
                elif self.handle_block:
                    prev_block = self.handle_block(e)
                else:
                    raise e
            except KeyboardInterrupt:
                print("Interrupted on", machine.current_interaction)
                break
            else:
                break

    @on_event(TracerEvent.SYSCALL_START, "read")
    def on_read_excess(self, syscall, args):
        if "io" not in self.current_interaction:
            current = self.current_interaction
            prev = self.prev_interaction
            if not prev:
                return
            prev_io = prev.get("io")
            if not prev_io or not prev_io.excess_data:
                return
            if current["syscall"] != prev["syscall"]:
                return
            if current["args"] != prev["args"]:
                return
            l.debug("Using previous excess data: %s", prev_io.excess_data)
            io = IO(prev_io.channel, prev_io.direction, prev_io.excess_data)
            self.current_interaction["io"] = io

        if "io" in self.current_interaction:
            count = int(args[2])
            io = self.current_interaction["io"]
            io.excess_data = io.data[count:]
            io.data = io.data[:count]
            if io.excess_data:
                l.debug("Separating excess data: %s", io.excess_data)

    @on_event(TracerEvent.SYSCALL_START, "read")
    def on_read_stdin(self, syscall, args):
        fd = int(args[0])
        if fd != 0:
            return
        if "io" not in self.current_interaction:
            self.current_interaction["io"] = IO("stdin", "read", None)
            raise Block(self, syscall, args)
        else:
            io = self.current_interaction["io"]
            self.stdin.write(io.data)
            self.stdin.flush()

    @on_event(TracerEvent.SYSCALL_FINISH, "write")
    def on_write_stdout(self, syscall, args, result):
        fd = int(args[0])
        if fd == 1:
            output = self.stdout.read(result)
            l.debug("stdout: %s", output)
            if result != len(output):
                raise Desync("stdout length", result, len(output))
            io = IO("stdout", "write", output)
            if "io" in self.prev_interaction:
                if self.prev_interaction["io"] != io:
                    raise Desync("stdout io", self.prev_interaction["io"], io)
            else:
                self.prev_interaction["io"] = io

    @on_event(TracerEvent.SYSCALL_FINISH, "write")
    def on_write_stderr(self, syscall, args, result):
        fd = int(args[0])
        if fd == 2:
            output = self.stderr.read(result)
            l.debug("stderr: %s", output)
            if result != len(output):
                raise Desync("stderr length", result, len(output))
            io = IO("stderr", "write", output)
            if "io" in self.prev_interaction:
                if self.prev_interaction["io"] != io:
                    raise Desync("stderr io", self.prev_interaction["io"], io)
            else:
                self.prev_interaction["io"] = io
