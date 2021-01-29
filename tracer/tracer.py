import os
import re
import subprocess
import enum
import json
import logging

import qtrace

l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))


class TracerEvent(enum.Enum):
    SYSCALL_START = enum.auto()
    SYSCALL_FINISH = enum.auto()
    EXEC_BLOCK = enum.auto()


event_count = 0


def on_event(event, filter_):
    global event_count

    def wrapper(func):
        if not hasattr(func, "on_event"):
            func.on_event = []
        func.on_event.append(
            {
                "id": event_count,
                "event": event,
                "filter": filter_,
            }
        )
        return func

    event_count += 1
    return wrapper


class Tracer(qtrace.TraceMachine):
    SYSCALL_ENABLED = True
    EXEC_BLOCK_ENABLED = True

    def __init__(self, argv, *, trace_socket=None, std_streams=(None, None, None)):
        super().__init__(argv, trace_socket=trace_socket, std_streams=std_streams)

        self.handlers = list()
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "on_event"):
                for handler in attr.on_event:
                    self.handlers.append((attr, handler))
        self.handlers = sorted(self.handlers, key=lambda k: k[1]["id"])

    def dispatch_event(self, event, *, syscall=None, args=None, result=None, addr=None):
        l.debug("Dispatching %s (%s)", event, hex(addr) if addr else syscall)
        for func, handler in self.handlers:
            handler_event = handler["event"]
            filter_ = handler["filter"]
            if handler_event != event:
                continue
            if event == TracerEvent.SYSCALL_START and re.match(
                "^" + filter_ + "$", syscall
            ):
                func(syscall, args)
            elif event == TracerEvent.SYSCALL_FINISH and re.match(
                "^" + filter_ + "$", syscall
            ):
                func(syscall, args, result)
            elif event == TracerEvent.EXEC_BLOCK and (
                filter_ is ... or addr in filter_
            ):
                func(addr)

    def run(self):
        execve_args = (
            json.dumps(self.argv[0]),
            json.dumps(self.argv),
            json.dumps({}),
        )
        self.dispatch_event(
            TracerEvent.SYSCALL_START, syscall="execve", args=execve_args
        )
        self.dispatch_event(
            TracerEvent.SYSCALL_FINISH,
            syscall="execve",
            args=execve_args,
            result=None,
        )
        super().run()

    def on_basic_block(self, address):
        self.dispatch_event(TracerEvent.EXEC_BLOCK, addr=address)

    def on_syscall_start(self, syscall_nr, *args):
        syscall = qtrace.syscalls["x86_64"][syscall_nr][1]
        syscall = syscall[len("sys_") :]
        self.dispatch_event(TracerEvent.SYSCALL_START, syscall=syscall, args=args)
        self.current_syscall = (syscall_nr, args)

    def on_syscall_end(self, syscall_nr, ret):
        current_syscall_nr, current_args = self.current_syscall
        assert syscall_nr == current_syscall_nr
        del self.current_syscall
        syscall = qtrace.syscalls["x86_64"][syscall_nr][1]
        syscall = syscall[len("sys_") :]
        self.dispatch_event(
            TracerEvent.SYSCALL_FINISH,
            syscall=syscall,
            args=current_args,
            result=ret,
        )
