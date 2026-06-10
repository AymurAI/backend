import torch

from aymurai.api import utils
from aymurai.settings import settings


def test_pipeline_memory_cache_uses_configured_ttl():
    assert utils.mem_cache.ttl == settings.MEMORY_CACHE_TTL


def test_configure_torch_threads_calls_torch_api(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "TORCH_NUM_THREADS", 3)
    monkeypatch.setattr(torch, "set_num_threads", calls.append)

    utils.configure_torch_threads()

    assert calls == [3]
