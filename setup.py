import os
import subprocess

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import tracer.qemu.build
tracer.qemu.build.build()

setup(
    name='cartprograph',
    python_requires='>=3.8',
    version='0.1.1',
    packages=[
        'tracer',
        'tracer.qemu',
    ],
    package_data={
        'tracer.qemu': ['bin/*'],
    },
    install_requires=[
        'flask',
        'flask_socketio',
        'eventlet',
    ]
)
