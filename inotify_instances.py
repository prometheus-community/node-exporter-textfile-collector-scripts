#!/usr/bin/env python3

"""
Expose Linux inotify(7) instance resource consumption.

Operational properties:

  - This script may be invoked as an unprivileged user; in this case, metrics
    will only be exposed for processes owned by that unprivileged user.

  - No metrics will be exposed for processes that do not hold any inotify fds.

Requires Python 3.5 or later.
"""

import argparse
import collections
import os
import re
import sys

from prometheus_client import CollectorRegistry, Gauge, generate_latest

__doc__ = "Exponse Linux Kernel inode information as Prometheus metrics."
_NotifyTarget = "anon_inode:inotify"
_Proc = "/proc"
_CommFile = "cmdline"
_StatsFile = "status"
_DescriptorDir = "fd"


class Error(Exception):
    pass


class _PIDGoneError(Error):
    pass


_Process = collections.namedtuple(
    "Process", ["pid", "uid", "command", "inotify_instances"]
)


def _read_bytes(name):
    with open(name, mode="rb") as f:
        return f.read()


def _pids(proc=_Proc):
    for n in os.listdir(proc):
        if not n.isdigit():
            continue
        yield int(n)


def _pid_uid(status):
    try:
        s = os.stat(status)
    except FileNotFoundError:
        raise _PIDGoneError()
    return s.st_uid


def _pid_command(cmdline):
    # Avoid GNU ps(1) for it truncates comm.
    # https://bugs.launchpad.net/ubuntu/+source/procps/+bug/295876/comments/3
    try:
        cmdline = _read_bytes(cmdline)
    except FileNotFoundError:
        raise _PIDGoneError()

    if not len(cmdline):
        return "<zombie>"

    try:
        prog = cmdline[0:cmdline.index(0x00)]
    except ValueError:
        prog = cmdline
    return os.path.basename(prog).decode(encoding="ascii", errors="surrogateescape")


def _pid_inotify_instances(descriptors):
    instances = 0
    try:
        for fd in os.listdir(descriptors):
            try:
                target = os.readlink(os.path.join(descriptors, fd))
            except FileNotFoundError:
                continue
            if target == _NotifyTarget:
                instances += 1
    except FileNotFoundError:
        raise _PIDGoneError()
    return instances


def _get_processes(proc=_Proc):
    for p in _pids(proc):
        try:
            pid = str(p)
            status = os.path.join(proc, pid, _StatsFile)
            cmdline = os.path.join(proc, pid, _CommFile)
            descriptors = os.path.join(proc, pid, _DescriptorDir)
            yield _Process(
                p,
                _pid_uid(status),
                _pid_command(cmdline),
                _pid_inotify_instances(descriptors),
            )
        except (PermissionError, _PIDGoneError):
            continue


def _generate_process_metrics(command=None, users=[], proc=_Proc):
    registry = CollectorRegistry()
    namespace = "inotify"

    g = Gauge(
        "instances",
        "Total number of inotify instances held open by a process.",
        ["pid", "uid", "command"],
        namespace=namespace,
        registry=registry,
    )

    for proc in _get_processes(proc):
        if proc.inotify_instances <= 0:
            continue
        elif users and proc.uid not in users:
            continue
        elif command and not command.match(proc.command):
            continue

        g.labels(proc.pid, proc.uid, proc.command).set(proc.inotify_instances)

    return generate_latest(registry).decode()


def _generate_user_metrics(users=[], proc=_Proc):
    registry = CollectorRegistry()
    namespace = "inotify"

    g = Gauge(
        "user_instances",
        "Total number of inotify instances held open by a user.",
        ["uid"],
        namespace=namespace,
        registry=registry,
    )

    for proc in _get_processes(proc):
        if proc.inotify_instances <= 0:
            continue
        elif users and proc.uid not in users:
            continue

        g.labels(proc.uid).inc()

    return generate_latest(registry).decode()


def main(argv=[__name__]):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        exit_on_error=False,
        description=__doc__,
    )
    parser.add_argument(
        "-c",
        "--command",
        default=".+",
        type=re.compile,
        dest="command",
        metavar="REGEX",
        help="Filter metrics based on the process command",
    )
    parser.add_argument(
        "-u",
        "--user",
        action="append",
        type=int,
        dest="users",
        metavar="UID",
        help="Filter metrics based on the process user",
    )
    parser.add_argument(
        "-U",
        "--user-summary",
        action="store_true",
        dest="user_summary",
        help="Generate per-user metric summaries instead of per process",
    )

    try:
        args = parser.parse_args(argv[1:])
    except argparse.ArgumentError as err:
        print(err, file=sys.stderr)
        return 1

    if args.user_summary:
        print(_generate_user_metrics(args.users), end="")
    else:
        print(_generate_process_metrics(args.command, args.users), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
