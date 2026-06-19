import textwrap
from datetime import datetime, timezone, timedelta
from xtools import post_tweet, postfile

JST = timezone(timedelta(hours=9))


class FakeClient:
    def __init__(self):
        self.calls = []

    def post_thread(self, tweets):
        self.calls.append(list(tweets))
        return [f"id{i}" for i, _ in enumerate(tweets)]


def _approved(tmp_path, name, body, scheduled="2026-06-20T09:00:00+09:00", thread=False):
    p = tmp_path / name
    p.write_text(textwrap.dedent(f"""\
        ---
        status: 承認済み
        scheduled_at: "{scheduled}"
        category: 技術ログ
        thread: {str(thread).lower()}
        tweet_ids: []
        ---
        # 投稿文
        {body}
        """), encoding="utf-8")
    return p


def test_post_due_posts_and_updates(tmp_path):
    _approved(tmp_path, "a.md", "テスト本文")
    ledger = tmp_path / "ledger.json"
    client = FakeClient()
    now = datetime(2026, 6, 20, 9, 0, tzinfo=JST)
    results = post_tweet.post_due(
        now=now, client=client, post_dir=tmp_path, ledger_path=ledger, do_git=False
    )
    assert results == [("a.md", "posted", ["id0"])]
    assert client.calls == [["テスト本文"]]
    reparsed = postfile.parse_post(tmp_path / "a.md")
    assert reparsed.status == postfile.STATUS_POSTED
    assert reparsed.tweet_ids == ["id0"]
    assert ledger.exists()


def test_post_due_is_idempotent_via_ledger(tmp_path):
    _approved(tmp_path, "a.md", "テスト本文")
    ledger = tmp_path / "ledger.json"
    now = datetime(2026, 6, 20, 9, 0, tzinfo=JST)
    post_tweet.post_due(now=now, client=FakeClient(), post_dir=tmp_path, ledger_path=ledger, do_git=False)
    second_client = FakeClient()
    results = post_tweet.post_due(now=now, client=second_client, post_dir=tmp_path, ledger_path=ledger, do_git=False)
    assert second_client.calls == []
    assert results == []


def test_post_due_skips_overlength(tmp_path):
    _approved(tmp_path, "long.md", "あ" * 141)
    ledger = tmp_path / "ledger.json"
    client = FakeClient()
    now = datetime(2026, 6, 20, 9, 0, tzinfo=JST)
    results = post_tweet.post_due(now=now, client=client, post_dir=tmp_path, ledger_path=ledger, do_git=False)
    assert results[0][0] == "long.md"
    assert results[0][1].startswith("error-overlength")
    assert client.calls == []


def test_post_due_dry_run_does_not_post(tmp_path):
    _approved(tmp_path, "a.md", "テスト本文")
    ledger = tmp_path / "ledger.json"
    client = FakeClient()
    now = datetime(2026, 6, 20, 9, 0, tzinfo=JST)
    results = post_tweet.post_due(
        now=now, client=client, post_dir=tmp_path, ledger_path=ledger, dry_run=True, do_git=False
    )
    assert results == [("a.md", "dry-run", [])]
    assert client.calls == []
    assert not ledger.exists()
