import importlib.util
from pathlib import Path

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

BASE_DIR = Path(__file__).resolve().parent

build_path = BASE_DIR / 'tracer' / 'qemu' / 'build.py'
spec = importlib.util.spec_from_file_location('build', build_path)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
build.build()

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
