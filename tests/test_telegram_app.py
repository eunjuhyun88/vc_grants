from __future__ import annotations

import pytest

from src.interface.telegram_app import SingleInstanceLock


def test_single_instance_lock_creates_and_releases_lockfile(tmp_path):
    lock_path = tmp_path / ".telegram-bot.lock"
    lock = SingleInstanceLock(lock_path)

    lock.acquire()
    assert lock_path.exists()
    assert lock_path.read_text(encoding="utf-8").strip()

    lock.release()
    assert not lock_path.exists()


def test_single_instance_lock_rejects_second_holder(tmp_path):
    lock_path = tmp_path / ".telegram-bot.lock"
    first = SingleInstanceLock(lock_path)
    second = SingleInstanceLock(lock_path)

    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="TELEGRAM_INSTANCE_CONFLICT"):
            second.acquire()
    finally:
        first.release()

