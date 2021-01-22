import pathlib
import pkg_resources


def qemu_base():
    return pkg_resources.resource_filename("tracer.qemu", "bin")


def qemu_path(arch):
    base = pathlib.Path(qemu_base()).resolve()
    path = base / f"qemu-{arch}"
    if not path.exists():
        raise ValueError(f"No qemu available for architecture `{arch}`")
    return path
