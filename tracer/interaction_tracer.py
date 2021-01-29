import os
import logging

from .tracer import Tracer, TracerEvent, on_event


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))


class Desync(Exception):
    def __init__(self, description, expected, received):
        self.description = description
        self.expected = expected
        self.received = received

    def __repr__(self):
        return f"<Desync {repr(self.description)}, expected={repr(self.expected)}, received={repr(self.received)}>"

    def __str__(self):
        return repr(self)


class InteractionTracer(Tracer):
    def __init__(
        self,
        argv,
        *,
        interaction=None,
        bb_trace=None,
        trace_socket=None,
        std_streams=(None, None, None),
    ):
        self.interaction = interaction if interaction is not None else list()
        self.interaction_index = 0
        self.bb_trace = bb_trace if bb_trace is not None else list()
        self.bb_trace_index = 0
        super().__init__(argv, trace_socket=trace_socket, std_streams=std_streams)

    @property
    def current_interaction(self):
        if self.interaction_index < len(self.interaction):
            return self.interaction[self.interaction_index]

    @property
    def prev_interaction(self):
        if 0 < self.interaction_index <= len(self.interaction):
            return self.interaction[self.interaction_index - 1]

    @property
    def prev_interactions(self):
        if 0 < self.interaction_index <= len(self.interaction):
            for i in range(self.interaction_index - 1, 0 - 1, -1):
                yield self.interaction[i]

    @property
    def stdin(self):
        return self.process.stdin if hasattr(self, "process") else None

    @property
    def stdout(self):
        return self.process.stdout if hasattr(self, "process") else None

    @property
    def stderr(self):
        return self.process.stderr if hasattr(self, "process") else None

    def run(self):
        self.interaction_index = 0
        super().run()

    @on_event(TracerEvent.EXEC_BLOCK, ...)
    def handle_exec_block(self, addr):
        if self.bb_trace_index < len(self.bb_trace):
            if self.bb_trace[self.bb_trace_index] != addr:
                raise Desync("exec addr", self.bb_trace[self.bb_trace_index], addr)
        else:
            self.bb_trace.append(addr)
        self.bb_trace_index += 1

    @on_event(TracerEvent.SYSCALL_START, ".*")
    def handle_syscall_start(self, syscall, args):
        l.debug("syscall: %s %s", syscall, args)
        if self.interaction_index < len(self.interaction):
            if self.current_interaction["syscall"] != syscall:
                raise Desync(
                    f"syscall ({syscall}, {args}) start",
                    self.current_interaction["syscall"],
                    syscall,
                )
            if self.current_interaction["args"] != args:
                raise Desync(
                    f"syscall ({syscall}, {args}) args start",
                    self.current_interaction["args"],
                    args,
                )
            if self.current_interaction["bb_trace_index"] != self.bb_trace_index:
                raise Desync(
                    f"syscall ({syscall}, {args}) bb_trace_index start",
                    self.current_interaction["bb_trace_index"],
                    self.bb_trace_index,
                )
        else:
            self.interaction.append(
                {
                    "syscall": syscall,
                    "args": args,
                    "bb_trace_index": self.bb_trace_index,
                }
            )

    @on_event(TracerEvent.SYSCALL_FINISH, ".*")
    def handle_syscall_end(self, syscall, args, result):
        l.debug("syscall: %s %s = %s", syscall, args, result)
        if self.current_interaction["syscall"] != syscall:
            raise Desync(
                f"syscall ({syscall}, {args}, {result}) finish",
                self.current_interaction["syscall"],
                syscall,
            )
        if self.current_interaction["args"] != args:
            raise Desync(
                f"syscall ({syscall}, {args}, {result}) args finish",
                self.current_interaction["args"],
                args,
            )
        if self.current_interaction["bb_trace_index"] != self.bb_trace_index:
            raise Desync(
                f"syscall ({syscall}, {args}, {result}) bb_trace_index finish",
                self.current_interaction["bb_trace_index"],
                self.bb_trace_index,
            )
        if "result" in self.current_interaction:
            if self.current_interaction["result"] != result:
                raise Desync(
                    f"syscall ({syscall}, {args}, {result}) result finish",
                    self.current_interaction["result"],
                    result,
                )
        else:
            self.current_interaction["result"] = result
        self.interaction_index += 1
