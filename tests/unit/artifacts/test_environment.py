"""Spec 2.6: `machine_id` names the host, the same in every process on it (#635)."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from nexusbt.artifacts import RunStore, _environment
from nexusbt.artifacts._environment import machine_id, same_machine

_PRINT_ID = "from nexusbt.artifacts._environment import machine_id; print(machine_id())"


def test_two_processes_on_one_host_give_the_same_machine_id() -> None:
    def one_process() -> str:
        done = subprocess.run(  # noqa: S603 - this interpreter and the literal above
            [sys.executable, "-c", _PRINT_ID], capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    assert one_process() == one_process()


def no_host_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, node: int) -> None:
    """A host with no machine-id file, no hardware UUID, and this node from uuid.getnode()."""
    monkeypatch.setattr(_environment, "_MACHINE_ID_FILES", (tmp_path / "machine-id",))
    monkeypatch.setattr(_environment, "_darwin_host_uuid", lambda: None)
    monkeypatch.setattr(uuid, "getnode", lambda: node)


def test_python_s_random_stand_in_node_is_not_a_host_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_host_id(monkeypatch, tmp_path, 0x0300_0000_0001)  # the multicast bit, bit 40, is set
    assert machine_id() is None


def test_a_hardware_address_is_a_host_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    no_host_id(monkeypatch, tmp_path, 0x0200_0000_0001)  # unicast
    assert machine_id() == "fe0a29e37dd070ea"  # printf 020000000001 | shasum -a 256


def test_a_run_sealed_without_a_host_id_records_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_host_id(monkeypatch, tmp_path, 0x0300_0000_0001)
    txn = RunStore(tmp_path / "runs").begin("backtest", "mom", None, graph_hash="g1", params={})
    manifest = json.loads((txn.seal().path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["environment"]["machine_id"] == "unknown"


def test_a_run_recorded_on_this_host_is_the_same_machine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_host_id(monkeypatch, tmp_path, 0x0200_0000_0001)
    assert same_machine("fe0a29e37dd070ea")
    assert not same_machine("0123456789abcdef")  # another host's id


@pytest.mark.parametrize("current", [None, "unknown"])  # the unread id, however it is spelled
def test_unknown_on_either_side_is_another_machine(
    monkeypatch: pytest.MonkeyPatch, current: str | None
) -> None:
    monkeypatch.setattr(_environment, "machine_id", lambda: current)
    assert not same_machine("unknown")  # neither host was identified: never a match
    assert not same_machine("fe0a29e37dd070ea")


def test_a_run_recorded_without_a_host_id_is_another_machine_here(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    no_host_id(monkeypatch, tmp_path, 0x0200_0000_0001)  # this host is identified
    assert not same_machine("unknown")
