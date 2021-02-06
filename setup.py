import importlib.util
from pathlib import Path

from setuptools import setup
from distutils.command.build import build as _build
from setuptools.command.develop import develop as _develop

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="cartprograph",
    python_requires=">=3.8",
    version="0.3.0",
    packages=[
        "cartprograph",
    ],
    install_requires=requirements,
)
