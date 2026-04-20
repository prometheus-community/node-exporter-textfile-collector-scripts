import os
import re

import pytest

import inotify_instances


class StatMock:
    def __init__(self, uid):
        self.uid = uid

    def __repr__(self):
        return f"StatMock(uid={self.uid})"

    def __call__(self, f):
        pid = os.path.basename(os.path.dirname(f))
        if pid == "1":
            # ensure at least one file is not affected by the mock
            # to generate some diversity
            return 0
        return self.uid


@pytest.fixture
def golden(request, golden):
    return golden.open(f"inotify_instances/{request.node.name}.yml")


@pytest.fixture
def proc():
    return os.path.abspath(
        os.path.join(__file__, "..", "..", "mock", "fixtures", "inotify_instances")
    )


@pytest.fixture
def stat():
    return StatMock(33)


def test__pids(proc, golden):
    pids = inotify_instances._pids(proc)

    assert sorted(list(pids)) == golden["output"]


def test__get_processes(proc, stat, golden):
    inotify_instances._pid_uid = stat
    procs = inotify_instances._get_processes(proc)

    assert sorted(map(str, procs)) == golden["output"]


def test_generate_process_metrics(proc, stat, golden):
    inotify_instances._pid_uid = stat
    command = re.compile(".+")
    output = inotify_instances._generate_process_metrics(command=command, proc=proc)

    assert output == golden["output"]


def test_generate_process_metrics_command(proc, stat, golden):
    inotify_instances._pid_uid = stat
    command = re.compile("systemd-.+")
    output = inotify_instances._generate_process_metrics(command=command, proc=proc)

    assert output == golden["output"]


def test_generate_process_metrics_no_command(proc, stat, golden):
    inotify_instances._pid_uid = stat
    command = re.compile("prom.+")
    output = inotify_instances._generate_process_metrics(command=command, proc=proc)

    assert output == golden["output"]


def test_generate_process_metrics_user(proc, stat, golden):
    inotify_instances._pid_uid = stat
    users = [0]
    output = inotify_instances._generate_process_metrics(users=users, proc=proc)

    assert output == golden["output"]


def test_generate_process_metrics_no_user(proc, stat, golden):
    inotify_instances._pid_uid = stat
    users = [42]
    output = inotify_instances._generate_process_metrics(users=users, proc=proc)

    assert output == golden["output"]


def test_generate_user_metrics(proc, stat, golden):
    inotify_instances._pid_uid = stat
    output = inotify_instances._generate_user_metrics(proc=proc)

    assert output == golden["output"]


def test_generate_user_metrics_user(proc, stat, golden):
    inotify_instances._pid_uid = stat
    users = [33]
    output = inotify_instances._generate_user_metrics(users=users, proc=proc)

    assert output == golden["output"]


def test_generate_user_metrics_no_user(proc, stat, golden):
    inotify_instances._pid_uid = stat
    users = [42]
    output = inotify_instances._generate_user_metrics(users=users, proc=proc)

    assert output == golden["output"]
