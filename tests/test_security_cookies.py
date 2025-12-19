from fastapi import Response

from app.utils import security


class DummySettings:
    session_cookie_name = "gifty_session"
    session_cookie_secure = False
    session_cookie_samesite = "lax"
    session_cookie_domain = None
    session_ttl_seconds = 60


def test_set_and_clear_cookie():
    settings = DummySettings()
    response = Response()

    security.set_session_cookie(response, "abc123", settings)
    cookies = response.headers.getlist("set-cookie")
    assert any("gifty_session=abc123" in c for c in cookies)
    assert any("HttpOnly" in c for c in cookies)

    security.clear_session_cookie(response, settings)
    cookies = response.headers.getlist("set-cookie")
    assert any("Max-Age=0" in c or "max-age=0" in c for c in cookies)

