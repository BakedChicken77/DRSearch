import asyncio

import pytest

from app import warmup


def test_warm_up_success(monkeypatch):
    warmup.INDEX_STATUS = {"idx": False}

    class Dummy:
        async def ainvoke(self, *_):
            return "ok"

    monkeypatch.setattr(warmup, "get_answer_chain", lambda name: Dummy())

    asyncio.run(warmup.warm_up_indexes())
    assert warmup.INDEX_STATUS["idx"] is True


def test_warm_up_failure(monkeypatch):
    warmup.INDEX_STATUS = {"idx": False}

    class Dummy:
        async def ainvoke(self, *_):
            raise ValueError("boom")

    monkeypatch.setattr(warmup, "get_answer_chain", lambda name: Dummy())

    asyncio.run(warmup.warm_up_indexes())
    assert warmup.INDEX_STATUS["idx"] is False
