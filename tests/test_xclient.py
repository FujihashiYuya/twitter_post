import pytest
from xtools.xclient import XClient, XAPIError


class FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def post(self, url, json=None, timeout=None):
        self.requests.append(("POST", url, json))
        return self._responses.pop(0)

    def get(self, url, params=None, timeout=None):
        self.requests.append(("GET", url, params))
        return self._responses.pop(0)


def test_create_tweet_returns_id():
    s = FakeSession([FakeResp(201, {"data": {"id": "100"}})])
    client = XClient(s, base="https://api.x.com/2")
    assert client.create_tweet("hello") == "100"
    assert s.requests[0][1] == "https://api.x.com/2/tweets"
    assert s.requests[0][2] == {"text": "hello"}


def test_post_thread_chains_replies():
    s = FakeSession([
        FakeResp(201, {"data": {"id": "100"}}),
        FakeResp(201, {"data": {"id": "101"}}),
    ])
    client = XClient(s, base="https://api.x.com/2")
    ids = client.post_thread(["one", "two"])
    assert ids == ["100", "101"]
    assert s.requests[1][2] == {"text": "two", "reply": {"in_reply_to_tweet_id": "100"}}


def test_create_tweet_raises_on_error():
    s = FakeSession([FakeResp(403, text="forbidden")])
    client = XClient(s, base="https://api.x.com/2")
    with pytest.raises(XAPIError):
        client.create_tweet("hello")


def test_get_metrics_maps_by_id():
    s = FakeSession([FakeResp(200, {"data": [
        {"id": "100", "public_metrics": {"impression_count": 500, "like_count": 10}},
    ]})])
    client = XClient(s, base="https://api.x.com/2")
    result = client.get_metrics(["100"])
    assert result["100"]["public_metrics"]["impression_count"] == 500


def test_create_tweet_raises_on_malformed_201_body():
    s = FakeSession([FakeResp(201, {"unexpected": "shape"})])
    client = XClient(s, base="https://api.x.com/2")
    with pytest.raises(XAPIError):
        client.create_tweet("hello")


def test_get_me_returns_id():
    s = FakeSession([FakeResp(200, {"data": {"id": "42"}})])
    client = XClient(s, base="https://api.x.com/2")
    assert client.get_me() == "42"
    assert s.requests[0][1] == "https://api.x.com/2/users/me"


def test_get_user_tweets_paginates_until_no_next_token():
    s = FakeSession([
        FakeResp(200, {"data": [{"id": "1"}], "meta": {"next_token": "t1"}}),
        FakeResp(200, {"data": [{"id": "2"}], "meta": {}}),
    ])
    client = XClient(s, base="https://api.x.com/2")
    tweets = client.get_user_tweets("42")
    assert [t["id"] for t in tweets] == ["1", "2"]
    assert s.requests[0][2]["exclude"] == "retweets"
    assert "pagination_token" not in s.requests[0][2]
    assert s.requests[1][2]["pagination_token"] == "t1"


def test_get_user_tweets_stops_at_max_pages():
    s = FakeSession([
        FakeResp(200, {"data": [{"id": "1"}], "meta": {"next_token": "t1"}}),
        FakeResp(200, {"data": [{"id": "2"}], "meta": {"next_token": "t2"}}),
    ])
    client = XClient(s, base="https://api.x.com/2")
    tweets = client.get_user_tweets("42", max_pages=2)
    assert len(tweets) == 2
    assert len(s.requests) == 2


def test_get_user_tweets_raises_on_error():
    s = FakeSession([FakeResp(429, text="rate limited")])
    client = XClient(s, base="https://api.x.com/2")
    with pytest.raises(XAPIError):
        client.get_user_tweets("42")


def test_get_metrics_batches_at_100():
    batch1 = [str(i) for i in range(100)]
    data1 = [{"id": i, "public_metrics": {}} for i in batch1]
    data2 = [{"id": "200", "public_metrics": {}}]
    s = FakeSession([
        FakeResp(200, {"data": data1}),
        FakeResp(200, {"data": data2}),
    ])
    client = XClient(s, base="https://api.x.com/2")
    result = client.get_metrics(batch1 + ["200"])
    assert len(result) == 101
    assert len(s.requests) == 2
