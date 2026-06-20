"""Per-IP rate limiting for the public API (abuse / scrape / DoS hardening).

A single global default limit is applied to every route via SlowAPIMiddleware;
/health is exempted in main.py so Render's health checks are never throttled.

Requests reach the app through the Vercel -> Render proxy chain, so the direct
peer is a proxy IP. The real client IP is the first hop of X-Forwarded-For;
fall back to the socket peer when the header is absent (e.g. local dev)."""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Generous by default: blocks scripted hammering without tripping on a human
# clicking around (a single workspace view can fire ~20-30 calls). Tunable via env.
RATE_LIMIT = os.getenv("RATE_LIMIT", "300/minute")


def client_ip(request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


# headers_enabled adds X-RateLimit-Limit/Remaining/Reset to every response so
# clients can see their budget (and it's an easy liveness signal in prod).
limiter = Limiter(key_func=client_ip, default_limits=[RATE_LIMIT], headers_enabled=True)
