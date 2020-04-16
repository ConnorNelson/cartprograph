import logging

from .tracer import Tracer, TracerEvent, on_event


l = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class InteractionTracer(Tracer):
    def __init__(self, target_args, *, interaction=None):
        self.interaction = interaction if interaction is not None else list()
        self.interaction_index = 0
        super().__init__(target_args)

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
            for i in range(self.interaction_index - 1, 0-1, -1):
                yield self.interaction[i]

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
        l.debug('syscall: %s %s', syscall, args)
        if self.interaction_index < len(self.interaction):
            assert self.current_interaction['syscall'] == syscall
            assert self.current_interaction['args'] == args
        else:
            self.interaction.append({
                'syscall': syscall,
                'args': args,
            })

    @on_event(TracerEvent.SYSCALL_FINISH, '.*')
    def on_syscall_finish(self, syscall, args, result):
        l.debug('syscall: %s %s = %s', syscall, args, result)
        assert self.current_interaction['syscall'] == syscall
        assert self.current_interaction['args'] == args
        if 'result' in self.current_interaction:
            assert self.current_interaction['result'] == result
        else:
            self.current_interaction['result'] = result
        self.interaction_index += 1
