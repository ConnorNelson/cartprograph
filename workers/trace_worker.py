#!/usr/bin/env python

import json

import redis

from tracer import IOBlockingTracer, IO, Block


def serialize_interaction(interaction):
    data = [{k: v for k, v in e.items()} for e in interaction]
    for e in data:
        if 'io' in e:
            io = e['io']
            e['io'] = {
                'channel': io.channel,
                'direction': io.direction,
                'data': io.data.decode('latin') if io.data is not None else None
            }
        if 'action' in e:
            del e['action']
    return data


def deserialize_interaction(interaction):
    for e in interaction:
        e['args'] = tuple(e['args'])
        if 'io' in e:
            io = e['io']
            io = IO(io['channel'], io['direction'], io['data'].encode('latin') if io['data'] is not None else None)
            e['io'] = io

            if io.channel == 'stdin' and io.direction == 'read' and io.data is not None:
                def action(machine, syscall, args, *, data=io.data):
                    if data:
                        machine.stdin.write(data)
                        machine.stdin.flush()
                    else:
                        machine.stdin.close()
                e['action'] = action

    return interaction


def main():
    r = redis.Redis(host='localhost', port=6379)

    while True:
        _, trace = r.blpop('work.trace')
        trace = json.loads(trace)

        interaction = deserialize_interaction(trace['interaction'])

        machine = IOBlockingTracer(['/bin/cat'],
                                   interaction=interaction)

        try:
            machine.run()

        except Block:
            trace['interaction'] = serialize_interaction(machine.interaction)
            trace = json.dumps(trace)
            r.publish('event.trace.blocked', trace)

        else:
            trace['interaction'] = serialize_interaction(machine.interaction)
            trace = json.dumps(trace)
            r.publish('event.trace.finished', trace)


if __name__ == '__main__':
    main()
