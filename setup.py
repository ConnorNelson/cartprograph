import importlib.util
from pathlib import Path

from setuptools import setup
from distutils.command.build import build as _build
from setuptools.command.develop import develop as _develop

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "requirements.txt") as f:
    requirements = f.read().splitlines()


def qemu_build():
    build_path = BASE_DIR / "tracer" / "qemu" / "build.py"
    spec = importlib.util.spec_from_file_location("build", build_path)
    build_qemu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_qemu)
    return build_qemu.build


class build(_build):
    def run(self):
        self.execute(qemu_build(), ())
        super().run()


class develop(_develop):
    def run(self):
        self.execute(qemu_build(), ())
        super().run()


setup(
    name="cartprograph",
    python_requires=">=3.8",
    version="0.2.3",
    packages=[
        "tracer",
        "tracer.qemu",
    ],
    package_data={
        "tracer.qemu": ["bin/*"],
    },
    install_requires=requirements,
    cmdclass={"build": build, "develop": develop},
)
