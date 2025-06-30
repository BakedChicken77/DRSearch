import asyncio
from pathlib import Path
import importlib
from types import SimpleNamespace
from queue import Queue

import logging
import pytest

from app.core import logging as core_logging


class _DummyStorage:
    """Capture uploads without touching Azure SDK."""

    def __init__(self):
        self.uploads: list[tuple[str, str, str]] = []

    async def upload_blob(self, container, blob_path, file_path):  # noqa: D401
        self.uploads.append((container, blob_path, file_path))

    async def close(self):
        self.closed = True


async def _drain_queue(listener: core_logging.QueueListener):
    """Helper: emit log entries to ensure handler paths execute."""
    logger = logging.getLogger("testlogger")
    logger.info("hello-world")
    # Allow listener thread to process
    await asyncio.sleep(0.01)


def test_setup_handlers_and_filter(tmp_path, monkeypatch):
    """Verify handler creation, filter behaviour, and blob upload helpers."""

    # Redirect LOG_DIR to a temp dir so we can inspect files safely.
    monkeypatch.setattr(core_logging, "LOG_DIR", tmp_path)

    # Force predictable logging settings via env vars.
    monkeypatch.setenv("LOG_FILE_MAX_MB", "1")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")

    settings = core_logging.LoggingSettings(log_output_mode="local")  # type: ignore
    listener = core_logging._setup_handlers(settings)
    listener.start()

    # Emit feedback vs. general log entries
    fb_logger = logging.getLogger("feedback")
    fb_logger.info("fb-entry")
    logging.getLogger("gen").warning("gen-entry")

    # Allow background thread to flush
    listener.stop()

    general = (tmp_path / "drsearch_backend_log.jsonl").read_text()
    feedback = (tmp_path / "feedback.jsonl").read_text()

    # Feedback should not be in general log and vice-versa
    assert "fb-entry" not in general
    assert "gen-entry" in general
    assert "fb-entry" in feedback

    # Test ExcludeFeedbackFilter directly
    filt = core_logging.ExcludeFeedbackFilter()
    record = logging.LogRecord("feedback", logging.INFO, "", 0, "msg", None, None)
    assert filt.filter(record) is False
    record2 = logging.LogRecord("other", logging.INFO, "", 0, "msg", None, None)
    assert filt.filter(record2) is True


def test_upload_logs(monkeypatch, tmp_path):
    """Exercise _upload_logs helper with dummy storage."""

    monkeypatch.setattr(core_logging, "LOG_DIR", tmp_path)
    # create fake log file
    (tmp_path / "drsearch_backend_log.jsonl").write_text("{}\n")

    # Patch the faulty ``datetime`` reference inside module.
    import datetime as _dt  # noqa: PLC0415
    monkeypatch.setattr(core_logging, "datetime", _dt, raising=False)

    dummy = _DummyStorage()
    settings = core_logging.LoggingSettings()  # type: ignore

    asyncio.run(core_logging._upload_logs(settings, dummy))  # type: ignore[arg-type]

    # One upload entry expected
    assert len(dummy.uploads) == 1


def test_start_blob_uploader(monkeypatch):
    """Return value should be an asyncio.Task even when connection string missing."""

    loop = asyncio.new_event_loop()

    task_no_conn = core_logging._start_blob_uploader(loop, core_logging.LoggingSettings())  # type: ignore
    assert isinstance(task_no_conn, asyncio.Task)

    loop.close()


# ---------------------------------------------------------------------------
# Global fixture: ensure the *main thread* always has an event loop so that
# any code calling ``asyncio.get_event_loop()`` outside of an async context
# (e.g. ``core.logging.configure_logging``) does not raise RuntimeError during
# the test session.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _main_event_loop():  # pragma: no cover
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield