from pathlib import Path

import pytest

import run_test_flow as harness

SIGNAL = Path(harness.SIGNAL_FILE)


@pytest.fixture(autouse=True)
def clean_signal():
    SIGNAL.unlink(missing_ok=True)
    yield
    SIGNAL.unlink(missing_ok=True)


def test_read_signal_returns_empty_when_absent():
    assert harness._read_signal() == ""


def test_read_signal_normalizes_and_removes():
    SIGNAL.write_text(" YES ", encoding="utf-8")
    assert harness._read_signal() == "yes"
    assert not SIGNAL.exists()


@pytest.mark.asyncio
async def test_wait_for_signal_accepts_yes():
    SIGNAL.write_text("yes", encoding="utf-8")
    assert await harness.wait_for_signal(timeout_minutes=1) is True


@pytest.mark.asyncio
async def test_wait_for_signal_rejects_no():
    SIGNAL.write_text("no", encoding="utf-8")
    assert await harness.wait_for_signal(timeout_minutes=1) is False
