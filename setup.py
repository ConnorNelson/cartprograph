import importlib.util
from pathlib import Path

from setuptools import setup
from distutils.command.build import build as _build
from setuptools.command.develop import develop as _develop

BASE_DIR = Path(__file__).resolve().parent

build_path = BASE_DIR / 'tracer' / 'qemu' / 'build.py'
spec = importlib.util.spec_from_file_location('build', build_path)
build_qemu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_qemu)

class build(_build):
    def run(self):
        self.execute(build_qemu.build, ())
        super().run()

class develop(_develop):
    def run(self):
        self.execute(build_qemu.build, ())
        super().run()

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
        'setuptools',
        'flask',
        'flask_socketio',
        'eventlet',
    ],
    cmdclass={
        'build': build,
        'develop': develop
    }
)
