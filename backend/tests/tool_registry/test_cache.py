from __future__ import annotations

import pytest

from app.tool_center.exceptions import RegistryUnavailableError
from app.tool_registry.cache import RegistryCache

from tests.tool_registry._helpers import FakeClock, SnapshotLoader


def _make_cache(clock: FakeClock) -> RegistryCache:
    return RegistryCache(ttl_seconds=30, stale_query_ttl_seconds=86400, clock=clock)


def test_cache_serves_fresh_snapshot_without_reloading() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    assert cache.get_or_load(loader).revision == "r1"
    clock.advance(seconds=29)
    assert cache.get_or_load(loader).revision == "r1"
    assert loader.calls == 1


def test_cache_refreshes_after_thirty_seconds() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    assert cache.get_or_load(loader).revision == "r1"
    clock.advance(seconds=31)
    assert cache.get_or_load(loader).revision == "r2"
    assert loader.calls == 2


def test_cache_wraps_loader_failure_after_expiry() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    cache.get_or_load(loader)
    clock.advance(seconds=31)
    loader.failing = True
    with pytest.raises(RegistryUnavailableError):
        cache.get_or_load(loader)


def test_cache_empty_loader_failure_raises_unavailable() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    loader.failing = True
    cache = _make_cache(clock)

    with pytest.raises(RegistryUnavailableError):
        cache.get_or_load(loader)


def test_cache_successful_reload_refreshes_stable_fallback() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    cache.get_or_load(loader)
    clock.advance(seconds=31)
    cache.get_or_load(loader)
    assert cache.get_stable_fallback(clock.now()).revision == "r2"


def test_stable_fallback_served_within_twenty_four_hours() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    cache.get_or_load(loader)
    clock.advance(seconds=86400)
    assert cache.get_stable_fallback(clock.now()).revision == "r1"


def test_stale_snapshot_expires_after_twenty_four_hours() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    cache.get_or_load(loader)
    clock.advance(seconds=86401)
    with pytest.raises(RegistryUnavailableError):
        cache.get_stable_fallback(clock.now())


def test_invalidate_forces_reload_from_loader() -> None:
    clock = FakeClock()
    loader = SnapshotLoader(clock=clock)
    cache = _make_cache(clock)

    cache.get_or_load(loader)
    cache.invalidate()
    assert cache.get_or_load(loader).revision == "r2"
    assert loader.calls == 2
