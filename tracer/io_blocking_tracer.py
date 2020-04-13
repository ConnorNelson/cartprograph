from .tracer import TracerEvent, on_event
from .interaction_tracer import InteractionTracer


class IO:
    def __init__(self, channel, direction, data):
        self.channel = channel
        self.direction = direction
        self.data = data

    def __eq__(self, other):
        return (type(self) is type(other) and
                self.channel == other.channel and
                self.direction == other.direction and
                self.data == other.data)

    def __repr__(self):
        return f'<IO channel={self.channel} direction={self.direction} data={self.data}>'


class Block(Exception):
    def __init__(self, machine, syscall, args, result=None):
        self.machine = machine
        self.syscall = syscall
        self.args = args
        self.result = result


class IOBlockingTracer(InteractionTracer):
    def __init__(self, target_args, handle_block=None, *, interaction=None):
        super().__init__(target_args, interaction=interaction)
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
                print('Interrupted on', machine.current_interaction)
                break
            else:
                break

    @property
    def prev_interaction(self):
        if 0 < self.interaction_index <= len(self.interaction):
            return self.interaction[self.interaction_index - 1]

    @on_event(TracerEvent.SYSCALL_START, 'read')
    def on_read_stdin(self, syscall, args):
        fd = int(args[0])
        if 'action' not in self.current_interaction and fd == 0:
            self.current_interaction['io'] = IO('stdin', 'read', None)
            raise Block(self, syscall, args)

    @on_event(TracerEvent.SYSCALL_FINISH, 'write')
    def on_write_stdout(self, syscall, args, result):
        fd = int(args[0])
        if fd == 1:
            output = self.stdout.read(result)
            assert len(output) == result
            io = IO('stdout', 'write', output)
            if 'io' in self.prev_interaction:
                assert self.prev_interaction['io'] == io
            else:
                self.prev_interaction['io'] = io

    @on_event(TracerEvent.SYSCALL_FINISH, 'write')
    def on_write_stderr(self, syscall, args, result):
        fd = int(args[0])
        if fd == 2:
            output = self.stdout.read(result)
            assert len(output) == result
            io = IO('stderr', 'write', output)
            if 'io' in self.prev_interaction:
                assert self.prev_interaction['io'] == io
            else:
                self.prev_interaction['io'] = io
