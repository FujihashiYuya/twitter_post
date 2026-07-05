import os

DEFAULT_BASE = os.environ.get("X_API_BASE", "https://api.x.com/2")


class XAPIError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(f"X API error {status}: {body}")
        self.status = status
        self.body = body


class XClient:
    def __init__(self, session, base: str | None = None):
        self.session = session
        self.base = (base or DEFAULT_BASE).rstrip("/")

    def create_tweet(self, text: str, in_reply_to: str | None = None) -> str:
        payload = {"text": text}
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        resp = self.session.post(f"{self.base}/tweets", json=payload, timeout=30)
        if resp.status_code != 201:
            raise XAPIError(resp.status_code, resp.text)
        try:
            return resp.json()["data"]["id"]
        except (KeyError, ValueError) as exc:
            raise XAPIError(resp.status_code, f"Unexpected response body: {resp.text}") from exc

    def post_thread(self, tweets: list[str]) -> list[str]:
        ids: list[str] = []
        reply_to = None
        for text in tweets:
            tid = self.create_tweet(text, in_reply_to=reply_to)
            ids.append(tid)
            reply_to = tid
        return ids

    def get_me(self) -> str:
        resp = self.session.get(f"{self.base}/users/me", timeout=30)
        if resp.status_code != 200:
            raise XAPIError(resp.status_code, resp.text)
        try:
            return resp.json()["data"]["id"]
        except (KeyError, ValueError) as exc:
            raise XAPIError(resp.status_code, f"Unexpected response body: {resp.text}") from exc

    def get_user_tweets(self, user_id: str, max_pages: int = 2) -> list[dict]:
        fields = "created_at,in_reply_to_user_id"
        tweets: list[dict] = []
        token = None
        for _ in range(max_pages):
            params = {"max_results": 100, "tweet.fields": fields, "exclude": "retweets"}
            if token:
                params["pagination_token"] = token
            resp = self.session.get(f"{self.base}/users/{user_id}/tweets", params=params, timeout=30)
            if resp.status_code != 200:
                raise XAPIError(resp.status_code, resp.text)
            body = resp.json()
            tweets.extend(body.get("data", []))
            token = body.get("meta", {}).get("next_token")
            if not token:
                break
        return tweets

    def get_metrics(self, tweet_ids: list[str]) -> dict:
        fields = "public_metrics,non_public_metrics,created_at"  # non_public_metrics requires user-context OAuth 1.0a + tweet ownership
        results: dict = {}
        for i in range(0, len(tweet_ids), 100):
            batch = tweet_ids[i : i + 100]
            resp = self.session.get(
                f"{self.base}/tweets",
                params={"ids": ",".join(batch), "tweet.fields": fields},
                timeout=30,
            )
            if resp.status_code != 200:
                raise XAPIError(resp.status_code, resp.text)
            # X may return partial results: ids for deleted/unauthorized tweets appear
            # in resp.json().get("errors", []) and are intentionally omitted here.
            for item in resp.json().get("data", []):
                tid = item.get("id")
                if tid:
                    results[tid] = item
        return results
