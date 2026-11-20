"""Spec 2.6: `machine_id` names the host, the same in every process on it (#635)."""

from __future__ import annotations

import ctypes
import json
import multiprocessing
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from nexusbt.artifacts import RunStore, _environment
from nexusbt.artifacts._environment import machine_id, same_machine


def test_two_processes_on_one_host_give_the_same_machine_id() -> None:
    def one_process() -> str | None:
        spawn = multiprocessing.get_context("spawn")  # a fresh interpreter, not a fork
        with ProcessPoolExecutor(max_workers=1, mp_context=spawn) as pool:
            return pool.submit(machine_id).result()

    first = one_process()
    assert first is not None  # this host has an id: the machine-id files, macOS, or a MAC
    assert one_process() == first


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


class FakeLibc:
    """macOS's libc as far as gethostuuid(2) goes: fills the 16 bytes, or fails with -1."""

    def __init__(self, answer: bytes | None) -> None:
        self.answer = answer

    def gethostuuid(self, found: ctypes.Array[ctypes.c_ubyte], _wait: object) -> int:
        if self.answer is None:
            return -1
        found[:] = list(self.answer)
        return 0


def on_a_mac(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, libc: FakeLibc) -> None:
    """A Mac with no machine-id file, this libc, and a unicast address from uuid.getnode()."""
    monkeypatch.setattr(_environment, "_MACHINE_ID_FILES", (tmp_path / "machine-id",))
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(ctypes, "CDLL", lambda _name: libc)
    monkeypatch.setattr(uuid, "getnode", lambda: 0x0200_0000_0001)


def test_on_macos_the_hardware_uuid_comes_before_the_address(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    on_a_mac(monkeypatch, tmp_path, FakeLibc(bytes([1] * 16)))
    # printf 01010101-0101-0101-0101-010101010101 | shasum -a 256
    assert machine_id() == "eb192cc58057209e"


def test_on_macos_a_failed_hardware_uuid_call_falls_to_the_address(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    on_a_mac(monkeypatch, tmp_path, FakeLibc(None))
    assert machine_id() == "fe0a29e37dd070ea"  # the address's id, as above


def test_a_hardware_uuid_call_that_cannot_be_made_is_unread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_libc(_name: object) -> object:
        raise OSError("no libc")

    monkeypatch.setattr(ctypes, "CDLL", no_libc)
    assert _environment._darwin_host_uuid() is None


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
