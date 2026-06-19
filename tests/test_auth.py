import pytest
from xtools.auth import make_session, MissingCredentialsError


def test_make_session_raises_when_missing(monkeypatch):
    for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(MissingCredentialsError):
        make_session()


def test_make_session_builds_oauth1(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "k")
    monkeypatch.setenv("X_API_SECRET", "s")
    monkeypatch.setenv("X_ACCESS_TOKEN", "t")
    monkeypatch.setenv("X_ACCESS_TOKEN_SECRET", "ts")
    session = make_session()
    assert session.auth.client.client_key == "k"
