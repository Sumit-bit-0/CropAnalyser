"""Rate-limiting: blocks past the limit, exempts /health, keys off the real
client IP (X-Forwarded-For) since traffic arrives via the Vercel->Render proxy."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from ratelimit import client_ip


def _app(limit: str) -> FastAPI:
    lim = Limiter(key_func=client_ip, default_limits=[limit])
    app = FastAPI()
    app.state.limiter = lim
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/health")
    @lim.exempt
    def health():
        return {"ok": True}

    return app


def test_blocks_after_limit():
    c = TestClient(_app("2/minute"))
    assert c.get("/ping").status_code == 200
    assert c.get("/ping").status_code == 200
    assert c.get("/ping").status_code == 429  # third call over the limit


def test_health_is_exempt():
    c = TestClient(_app("1/minute"))
    for _ in range(5):
        assert c.get("/health").status_code == 200


def test_client_ip_uses_first_forwarded_hop():
    req = SimpleNamespace(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert client_ip(req) == "1.2.3.4"


def test_separate_ips_get_separate_buckets():
    c = TestClient(_app("1/minute"))
    h1 = {"X-Forwarded-For": "11.11.11.11"}
    h2 = {"X-Forwarded-For": "22.22.22.22"}
    assert c.get("/ping", headers=h1).status_code == 200
    assert c.get("/ping", headers=h1).status_code == 429  # same IP, over limit
    assert c.get("/ping", headers=h2).status_code == 200  # different IP, fresh bucket
