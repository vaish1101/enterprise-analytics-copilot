"""Corpus-free API boundaries; no external requests or private fixtures."""
import pytest


def test_peer_quota_atomic_and_private(monkeypatch):
    from src.api.rate_limit import SlidingWindowLimiter
    from concurrent.futures import ThreadPoolExecutor
    clock=[100.0]
    monkeypatch.setattr('src.api.rate_limit.time.monotonic',lambda:clock[0])
    limiter=SlidingWindowLimiter(3)
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(limiter.allow,['192.0.2.1']*30))==3
    assert all('192.0.2' not in key for key in limiter._events)
    assert limiter.allow('192.0.2.2')
    clock[0]=161.0
    assert limiter.allow('192.0.2.1')


def test_public_api_without_private_assets(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from pathlib import Path
    from src.api.app import create_app
    from src.api.settings import AppSettings
    read=Path.read_text
    def guard(path,*args,**kwargs):
        assert 'data/retrieval/local' not in str(path)
        return read(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guard)
    settings=AppSettings(app_mode='demo',public_demo=True,
        checkpoint_uri=str(tmp_path/'checkpoint.sqlite'),session_db_path=str(tmp_path/'sessions.sqlite'))
    with TestClient(create_app(settings=settings)) as api:
        assert api.get('/ready').status_code==200
        numeric=api.post('/api/v1/query',json={'question':'What were Henkel H1 2026 sales?'}).json()
        refused=api.post('/api/v1/query',json={'question':'How does Henkel define organic sales growth?'}).json()
    assert numeric['status']=='COMPLETED' and numeric['provider']=='deterministic_fake'
    assert numeric['claims'][0]['value']=='10348'
    assert refused['status']=='REFUSED' and not refused['claims']


def test_demo_cannot_silently_enable_in_production():
    from src.api.settings import AppSettings
    with pytest.raises(ValueError):AppSettings(public_demo=True)
