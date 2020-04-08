import os
import subprocess

try:
    from setuptools import setup
    from setuptools import find_packages
    packages = find_packages()
except ImportError:
    from distutils.core import setup
    packages = [x.strip('./').replace('/', '.') for x in os.popen('find -name "__init__.py" | xargs -n1 dirname').read().strip().split('\n')]

setup(
      name='cartprograph',
      python_requires='>=3.8',
      version='0.1.0',
      packages=packages,
      install_requires=[
          'flask',
          'flask_socketio',
          'eventlet',
      ],
      dependency_links=[
      ],
)
