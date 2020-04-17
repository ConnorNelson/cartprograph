#!/usr/bin/env python

import os
import re
import pathlib
import json
import logging

import redis
import archr

import tracer.qemu
from tracer import IOBlockingTracer, IO, Block, on_event, TracerEvent


l = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))


class IOBlockingArchrTracer(tracer.IOBlockingTracer):
    def __init__(self, target, interaction, bb_trace):
        super().__init__(target.target_args,
                         interaction=interaction,
                         bb_trace=bb_trace)
        self.target = target
        self.fd_channels = {}

    def start(self):
        qemu_path_src = tracer.qemu.qemu_path(self.target.target_arch)
        qemu_path = pathlib.Path(self.target.tmpwd) / qemu_path_src.name
        self.target.inject_path(qemu_path_src, qemu_path)

        log_path = pathlib.Path(self.target.tmpwd) / 'qemu_log'
        self.target.run_command(['mkfifo', str(log_path)]).wait()
        log_popen = self.target.run_command(['cat', str(log_path)])

        qemu_args = [str(qemu_path), '-d', 'strace,exec',
                     '-D', str(log_path),
                     '--', *self.target.target_args]

        flight = self.target.flight(qemu_args)

        self.flight = flight
        self.log_popen = log_popen

        return flight.process, log_popen.stdout.fileno()

    def stop(self):
        self.flight.process.kill()
        self.log_popen.kill()

    @on_event(TracerEvent.SYSCALL_START, 'accept')
    def on_accept(self, syscall, args):
        fd = int(args[0])
        for interaction in self.prev_interactions:
            if interaction['syscall'] == 'bind':
                bind_args = interaction['args']
                bind_fd = int(bind_args[0])
                if bind_fd != fd:
                    continue
                match = re.search(r'sin_port=htons\((?P<port>\d+)\)', bind_args[2])
                if not match:
                    continue
                port = int(match['port'])
                if not port in self.target.tcp_ports:
                    raise Exception('Target is listening on port %d, but archr is not aware of it', port)
                l.info('Connecting to port %d', port)
                port_index = self.target.tcp_ports.index(port)
                channel_name = f'tcp:{port_index}'
                self.flight.get_channel(channel_name)
                self.fd_channels[fd] = channel_name
                return

    @on_event(TracerEvent.SYSCALL_FINISH, 'accept')
    def on_accept_finished(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            channel = self.fd_channels[fd]
            del self.fd_channels[fd]
            self.fd_channels[result] = channel

    @on_event(TracerEvent.SYSCALL_START, 'read')
    def on_read_socket(self, syscall, args):
        fd = int(args[0])
        if fd not in self.fd_channels:
            return
        channel_name = self.fd_channels[fd]
        port_index = int(channel_name.split(':')[1])
        port = self.target.tcp_ports[port_index]
        if 'io' not in self.current_interaction:
            self.current_interaction['io'] = IO(f'tcp:{port}', 'read', None)
            raise Block(self, syscall, args)
        else:
            io = self.current_interaction['io']
            channel = self.flight.get_channel(channel_name)
            if io.data:
                l.debug('tcp:%d read: %s', port, io.data)
                channel.write(io.data)
            else:
                l.debug('tcp:%d read: shutdown_wr', port)
                channel.shutdown_wr()

    @on_event(TracerEvent.SYSCALL_FINISH, 'write')
    def on_write_socket(self, syscall, args, result):
        fd = int(args[0])
        if fd in self.fd_channels:
            channel_name = self.fd_channels[fd]
            port_index = int(channel_name.split(':')[1])
            port = self.target.tcp_ports[port_index]
            channel = self.flight.get_channel(channel_name)
            output = channel.read(result)
            l.debug('tcp:%d write: %s', port, output)
            assert len(output) == result
            io = IO(f'tcp:{port}', 'write', output)
            if 'io' in self.prev_interaction:
                assert self.prev_interaction['io'] == io
            else:
                self.prev_interaction['io'] = io


def serialize_interaction(interaction):
    data = [{k: v for k, v in e.items()} for e in interaction]
    for e in data:
        if 'io' in e:
            io = e['io']
            e['io'] = {
                'channel': io.channel,
                'direction': io.direction,
                'data': io.data.decode('latin') if io.data is not None else None,
            }
    return data


def deserialize_interaction(interaction):
    for e in interaction:
        e['args'] = tuple(e['args'])
        if 'io' in e:
            io = e['io']
            io = IO(io['channel'], io['direction'],
                    io['data'].encode('latin') if io['data'] is not None else None)
            e['io'] = io
    return interaction


def main():
    r = redis.Redis(host='localhost', port=6379)

    while True:
        _, trace = r.blpop('work.trace')
        trace = json.loads(trace)

        interaction = deserialize_interaction(trace['interaction'])
        bb_trace = trace['bb_trace']

        with archr.targets.DockerImageTarget('irving').build().start() as target:
            machine = IOBlockingArchrTracer(target,
                                            interaction=interaction,
                                            bb_trace=bb_trace)

            def publish_trace(channel):
                nonlocal trace
                trace['interaction'] = serialize_interaction(machine.interaction)
                trace['bb_trace'] = machine.bb_trace
                trace = json.dumps(trace)
                r.publish(channel, trace)

            try:
                machine.run()

            except Block:
                publish_trace('event.trace.blocked')

            except Exception:
                publish_trace('event.trace.desync')

            else:
                publish_trace('event.trace.finished')

if __name__ == '__main__':
    main()
