"""The per-port lock has one owner and does not become stale after that owner ends."""

import sys

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX lock behavior")
def test_a_posix_port_lock_can_be_acquired_after_the_owner_closes_it(tmp_path):
    from ozvuchka.instance_posix import PosixPortLock

    first = PosixPortLock(8770, tmp_path)
    second = PosixPortLock(8770, tmp_path)

    assert first.acquire() is True
    assert second.acquire() is False
    first.close()
    assert second.acquire() is True
    second.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX lock behavior")
def test_a_remaining_posix_lock_file_does_not_block_a_new_owner(tmp_path):
    from ozvuchka.instance_posix import PosixPortLock

    lock_path = tmp_path / "instance-8770.lock"
    lock_path.write_text("stale file contents", encoding="ascii")
    lock = PosixPortLock(8770, tmp_path)

    assert lock.acquire() is True
    lock.close()
