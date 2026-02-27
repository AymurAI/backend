import diskcache
import pytest
from sqlmodel import SQLModel, create_engine


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def isolated_diskcache(tmp_path):
    from aymurai.utils import cache as cache_module

    original_cache = cache_module.cache
    test_cache = diskcache.Cache(str(tmp_path / "diskcache"))
    cache_module.cache = test_cache
    yield test_cache
    cache_module.cache = original_cache
    test_cache.close()
