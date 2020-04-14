import os
import re
import subprocess
import enum
import json
import logging

from .qemu import qemu_path


l = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

QEMU_PATH = qemu_path('x86_64')


class RegexReader:
    def __init__(self, fd):
        self.fd = fd
        self._buffer = b''

    def unread(self, data):
        self._buffer = data + self._buffer

    def read_regex(self, *regexs):
        while True:
            matches = [
                re.search(regex, self._buffer)
                for regex in regexs
            ]
            if any(matches):
                match = sorted([match for match in matches if match], key=lambda k: k.start())[0]
                self._buffer = self._buffer[match.end():]
                return match
            self._buffer += os.read(self.fd, 4096)


class TracerEvent(enum.Enum):
    SYSCALL_START = enum.auto()
    SYSCALL_FINISH = enum.auto()
    EXEC_BLOCK = enum.auto()


event_count = 0
def on_event(event, filter_):
    global event_count
    def wrapper(func):
        if not hasattr(func, 'on_event'):
            func.on_event = []
        func.on_event.append({
            'id': event_count,
            'event': event,
            'filter': filter_,
        })
        return func
    event_count += 1
    return wrapper


class Tracer:
    SYSCALL_ENABLED = True
    EXEC_BLOCK_ENABLED = True

    def __init__(self, target_args):
        self.target_args = target_args

        self.handlers = list()
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, 'on_event'):
                for handler in attr.on_event:
                    self.handlers.append((attr, handler))
        self.handlers = sorted(self.handlers, key=lambda k: k[1]['id'])

    def dispatch_event(self, event, *, syscall=None, args=None, result=None, addr=None):
        l.debug('Dispatching %s (%s)', event, hex(addr) if addr else syscall)
        for func, handler in self.handlers:
            handler_event = handler['event']
            filter_ = handler['filter']
            if handler_event != event:
                continue
            if event == TracerEvent.SYSCALL_START and re.match('^' + filter_ + '$', syscall):
                func(syscall, args)
            elif event == TracerEvent.SYSCALL_FINISH and re.match('^' + filter_ + '$', syscall):
                func(syscall, args, result)
            elif event == TracerEvent.EXEC_BLOCK and (filter_ is ... or addr in filter_):
                func(addr)

    def run(self):
        qemu_log_r, qemu_log_w = os.pipe()
        qemu_log_path = f'/proc/{os.getpid()}/fd/{qemu_log_w}'

        log_options = []
        if self.SYSCALL_ENABLED:
            log_options.append('strace')
        if self.EXEC_BLOCK_ENABLED:
            log_options.append('exec')

        popen = subprocess.Popen([QEMU_PATH, '-d', ','.join(log_options),
                                  '-D', qemu_log_path,
                                  '--', *self.target_args],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        self.popen = popen

        reader = RegexReader(qemu_log_r)

        try:
            execve_args = (json.dumps(self.target_args[0]),
                           json.dumps(self.target_args),
                           json.dumps({}))
            self.dispatch_event(TracerEvent.SYSCALL_START, syscall='execve', args=execve_args)
            self.dispatch_event(TracerEvent.SYSCALL_FINISH, syscall='execve', args=execve_args, result=None)

            while True:
                # syscall_re is very delicate because args terminator ')' can and does appear inside an arg
                # ?P<args> tries to find args that end with ' =', as this appears before the return result
                # ?P<args_blocked> handles the case where the syscall is blocked, which will not end in ' ='
                # in this case, the line must end with a ')'
                # line end must occur because otherwise potential race condition could occur in non-blocked syscall midway through logging it
                # fortunately, this should be mitigated by a ',' if there are more args
                syscall_re = br'(?P<pid>\d+) (?P<syscall>\w+)((\((?P<args>.*?)\)(?= =))|(\((?P<args_blocked>.*?)\)$))'
                syscall_result_re = br' = (?P<result>.*)\n'
                bb_addr_re = br'Trace .*?: .*? \[.*?\/(?P<addr>.*?)\/.*?\] \n'

                match = reader.read_regex(syscall_re, bb_addr_re)

                if match.groupdict().get('addr'):
                    bb_addr_match = match
                    addr = int(bb_addr_match['addr'], 16)
                    self.dispatch_event(TracerEvent.EXEC_BLOCK, addr=addr)

                elif match.groupdict().get('syscall'):
                    syscall_match = match
                    pid = int(syscall_match['pid'].decode())
                    syscall = syscall_match['syscall'].decode()
                    if syscall_match['args'] is not None:
                        args = syscall_match['args']
                    else:
                        args = syscall_match['args_blocked']
                    args = tuple(arg.strip() for arg in args.decode().split(','))

                    self.dispatch_event(TracerEvent.SYSCALL_START, syscall=syscall, args=args)

                    if 'exit' in syscall:
                        break

                    syscall_result_match = reader.read_regex(syscall_result_re)
                    result, _, result_info = syscall_result_match['result'].decode().partition(' ')
                    result = int(result, 16) if result.startswith('0x') else int(result)

                    self.dispatch_event(TracerEvent.SYSCALL_FINISH, syscall=syscall, args=args, result=result)

        finally:
            popen.kill()
            popen.stdin.close()
            popen.stdout.close()
            popen.stderr.close()
            os.close(qemu_log_r)
            os.close(qemu_log_w)
