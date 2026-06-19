import os

from requests_oauthlib import OAuth1Session


class MissingCredentialsError(RuntimeError):
    pass


_REQUIRED = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]


def make_session() -> OAuth1Session:
    vals = {k: os.environ.get(k) for k in _REQUIRED}
    missing = [k for k, v in vals.items() if not v]
    if missing:
        raise MissingCredentialsError(f"Missing env vars: {', '.join(missing)}")
    return OAuth1Session(
        client_key=vals["X_API_KEY"],
        client_secret=vals["X_API_SECRET"],
        resource_owner_key=vals["X_ACCESS_TOKEN"],
        resource_owner_secret=vals["X_ACCESS_TOKEN_SECRET"],
    )
