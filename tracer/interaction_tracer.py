from .tracer import Tracer, TracerEvent, on_event


class InteractionTracer(Tracer):
    def __init__(self, target_args):
        self.interaction = list()
        self.interaction_index = 0
        super().__init__(target_args)

    @property
    def current_interaction(self):
        if self.interaction_index < len(self.interaction):
            return self.interaction[self.interaction_index]

    @property
    def stdin(self):
        return self.popen.stdin if hasattr(self, 'popen') else None

    @property
    def stdout(self):
        return self.popen.stdout if hasattr(self, 'popen') else None

    @property
    def stderr(self):
        return self.popen.stderr if hasattr(self, 'popen') else None

    def run(self):
        self.interaction_index = 0
        super().run()

    @on_event(TracerEvent.SYSCALL_START, '.*')
    def on_syscall_start(self, syscall, args):
        if self.interaction_index < len(self.interaction):
            assert self.current_interaction['syscall'] == syscall
            assert self.current_interaction['args'] == args

            if 'action' in self.current_interaction:
                self.current_interaction['action'](self, syscall, args)

        else:
            self.interaction.append({
                'syscall': syscall,
                'args': args,
            })

    @on_event(TracerEvent.SYSCALL_FINISH, '.*')
    def on_syscall_finish(self, syscall, args, result):
        assert self.current_interaction['syscall'] == syscall
        assert self.current_interaction['args'] == args
        if 'result' in self.current_interaction:
            assert self.current_interaction['result'] == result
        else:
            self.current_interaction['result'] = result
        self.interaction_index += 1
