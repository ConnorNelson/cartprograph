#!/usr/bin/env python

from sys import executable
from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import check_call


BASE_DIR = Path(__file__).resolve().parent
PATCHES_DIR = BASE_DIR / "patches"
BIN_DIR = BASE_DIR / "bin"

QEMU_REPO = "https://github.com/qemu/qemu.git"
QEMU_BRANCH = "v5.0.0-rc1"
QEMU_TARGETS = [
    # 'i386-linux-user',
    "x86_64-linux-user",
    # 'mips-linux-user',
    # 'mips64-linux-user',
    # 'mipsel-linux-user',
    # 'ppc-linux-user',
    # 'ppc64-linux-user',
    # 'arm-linux-user',
    # 'aarch64-linux-user',
]


def build(rebuild=False):
    if not rebuild and BIN_DIR.exists() and list(BIN_DIR.iterdir()):
        return

    with TemporaryDirectory() as work_dir:
        check_call(
            ["git", "clone", "--depth=1", "--branch", QEMU_BRANCH, QEMU_REPO, work_dir]
        )

        for patch in PATCHES_DIR.iterdir():
            check_call(["git", "-C", work_dir, "apply", patch])

        targets = ",".join(QEMU_TARGETS)
        check_call(
            [
                "./configure",
                "--static",
                f"--target-list={targets}",
                f"--python={executable}",
                "--disable-werror",
            ],
            cwd=work_dir,
        )

        check_call(["make", "-j4"], cwd=work_dir)

        BIN_DIR.mkdir(exist_ok=True)

        for target in QEMU_TARGETS:
            arch = target.split("-")[0]
            qemu_bin = Path(work_dir) / target / f"qemu-{arch}"
            qemu_bin.replace(BIN_DIR / qemu_bin.name)


if __name__ == "__main__":
    build()
