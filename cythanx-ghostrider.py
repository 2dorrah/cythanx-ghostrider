#!/usr/bin/env python3
"""
CYTHANX/XMRig GhostRider automated builder + launcher.

What this script does:
  1. Clones/updates the official XMRig source tree.
  2. Builds XMRig with native GhostRider and hwloc support.
  3. Starts XMRig against the configured GhostRider Stratum endpoint.
  4. Leaves the CYTHANX blockchain logic separate; XMRig handles pool
     protocol and native GhostRider hashing.

The actual GhostRider implementation is XMRig's native C/C++ implementation.
This script does not replace it with Python Scrypt or a fake hash.

Environment overrides:
  XMRIG_DIR       source/build root (default: ./xmrig)
  POOL_URL        default: stratum+tcp://ghostrider.unmineable.com:3333
  NANO_ADDRESS    default: supplied Nano payout address
  WORKER_NAME     default: cythanx5
  POOL_PASSWORD   default: x
  CPU_HINT        optional integer 0..100
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/xmrig/xmrig.git"
ROOT = Path(os.environ.get("XMRIG_DIR", "./xmrig")).expanduser().resolve()
BUILD = ROOT / "build"

POOL_URL = os.environ.get(
    "POOL_URL",
    "stratum+tcp://ghostrider.unmineable.com:3333",
)
NANO_ADDRESS = os.environ.get(
    "NANO_ADDRESS",
    "nano_1m3m76uncsnxyid6awidp4wqktes9gq4jxug1aitetn38n6psq4h9k3gfwx1",
)
WORKER_NAME = os.environ.get("WORKER_NAME", "cythanx5")
POOL_PASSWORD = os.environ.get("POOL_PASSWORD", "x")
CPU_HINT = os.environ.get("CPU_HINT")

# unMineable-style username.
USERNAME = f"NANO:{NANO_ADDRESS}.{WORKER_NAME}"


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def require(command: str) -> None:
    if shutil.which(command) is None:
        die(f"required command not found: {command}")


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True)


def ensure_source() -> None:
    if (ROOT / ".git").is_dir():
        print(f"Updating existing XMRig source: {ROOT}")
        run("git", "pull", "--ff-only", cwd=ROOT)
    else:
        ROOT.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning XMRig into: {ROOT}")
        run("git", "clone", "--depth", "1", REPO, str(ROOT))


def build_xmrig() -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)

    run(
        "cmake",
        "..",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DWITH_GHOSTRIDER=ON",
        "-DWITH_HWLOC=ON",
        "-DWITH_OPENCL=OFF",
        "-DWITH_CUDA=OFF",
        cwd=BUILD,
    )

    jobs = str(max(1, os.cpu_count() or 1))
    run("cmake", "--build", ".", "--config", "Release", "-j", jobs, cwd=BUILD)

    candidates = [
        BUILD / "xmrig",
        BUILD / "Release" / "xmrig",
        BUILD / "xmrig.exe",
        BUILD / "Release" / "xmrig.exe",
    ]

    for binary in candidates:
        if binary.is_file():
            return binary

    die("XMRig build completed but the executable was not found.")
    raise AssertionError


def make_command(binary: Path) -> list[str]:
    cmd = [
        str(binary),
        "-a", "gr",
        "-o", POOL_URL,
        "-u", USERNAME,
        "-p", POOL_PASSWORD,
    ]

    if CPU_HINT:
        try:
            hint = int(CPU_HINT)
        except ValueError:
            die("CPU_HINT must be an integer from 0 to 100.")
        if not 0 <= hint <= 100:
            die("CPU_HINT must be between 0 and 100.")
        cmd += ["--cpu-max-threads-hint", str(hint)]

    return cmd


def main() -> int:
    for command in ("git", "cmake"):
        require(command)

    ensure_source()
    binary = build_xmrig()

    print()
    print("XMRig:", binary)
    print("Algorithm: GhostRider")
    print("Pool:", POOL_URL)
    print("User:", USERNAME)
    print()
    print("Starting native GhostRider miner. Press Ctrl-C to stop.")

    cmd = make_command(binary)
    print("+", " ".join(cmd))

    process = subprocess.Popen(cmd)

    def stop(_signum, _frame):
        if process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
