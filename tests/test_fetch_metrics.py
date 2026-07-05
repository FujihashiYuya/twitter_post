import csv
import textwrap
from datetime import datetime, timezone, timedelta
from xtools import fetch_metrics

JST = timezone(timedelta(hours=9))


class FakeMetricsClient:
    def __init__(self, data):
        self._data = data

    def get_metrics(self, ids):
        return {i: self._data[i] for i in ids if i in self._data}


def _posted(tmp_path, name, tweet_id, posted_at="2026-06-20T09:00:00+09:00"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(f"""\
        ---
        status: 投稿済み
        scheduled_at: "{posted_at}"
        category: 技術ログ
        thread: false
        posted_at: "{posted_at}"
        tweet_ids: ["{tweet_id}"]
        ---
        # 投稿文
        本文サンプル
        """), encoding="utf-8")
    return p


def test_fetch_writes_csv_with_metrics(tmp_path):
    _posted(tmp_path, "a.md", "100")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeMetricsClient({
        "100": {"public_metrics": {"impression_count": 800, "like_count": 12,
                                    "retweet_count": 2, "reply_count": 1, "quote_count": 0,
                                    "bookmark_count": 3}}
    })
    now = datetime(2026, 6, 21, 12, 0, tzinfo=JST)
    rows = fetch_metrics.fetch(now=now, client=client, post_dir=tmp_path, csv_path=csv_path)
    assert len(rows) == 1
    assert csv_path.exists()
    with csv_path.open(encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    assert records[0]["tweet_id"] == "100"
    assert records[0]["impressions"] == "800"
    assert records[0]["posted_weekday"] == "土"  # 2026-06-20 is Saturday
    assert records[0]["posted_hour"] == "9"


def test_fetch_appends_second_snapshot(tmp_path):
    _posted(tmp_path, "a.md", "100")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeMetricsClient({"100": {"public_metrics": {"impression_count": 800}}})
    fetch_metrics.fetch(now=datetime(2026, 6, 21, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    with csv_path.open(encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    assert len(records) == 2  # two weekly snapshots


def test_fetch_writes_header_when_csv_is_empty_file(tmp_path):
    _posted(tmp_path, "a.md", "100")
    csv_path = tmp_path / "metrics_log.csv"
    csv_path.write_text("", encoding="utf-8")  # pre-existing 0-byte file
    client = FakeMetricsClient({"100": {"public_metrics": {"impression_count": 5}}})
    fetch_metrics.fetch(now=datetime(2026, 6, 21, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    with csv_path.open(encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    assert records[0]["impressions"] == "5"  # header present -> DictReader maps correctly


def test_fetch_weekday_uses_jst_for_utc_posted_at(tmp_path):
    _posted(tmp_path, "a.md", "100", posted_at="2026-06-19T23:30:00+00:00")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeMetricsClient({"100": {"public_metrics": {"impression_count": 1}}})
    fetch_metrics.fetch(now=datetime(2026, 6, 21, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    with csv_path.open(encoding="utf-8") as f:
        rec = list(csv.DictReader(f))[0]
    assert rec["posted_weekday"] == "土"   # 2026-06-19 23:30 UTC == 2026-06-20 08:30 JST (Sat)
    assert rec["posted_hour"] == "8"


def test_fetch_reads_impressions_from_non_public_metrics(tmp_path):
    _posted(tmp_path, "a.md", "100")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeMetricsClient({
        "100": {
            "public_metrics": {"like_count": 4},
            "non_public_metrics": {"impression_count": 1234, "url_link_clicks": 7, "user_profile_clicks": 2},
        }
    })
    fetch_metrics.fetch(now=datetime(2026, 6, 21, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    import csv as _csv
    with csv_path.open(encoding="utf-8") as f:
        rec = list(_csv.DictReader(f))[0]
    assert rec["impressions"] == "1234"
    assert rec["likes"] == "4"
    assert rec["url_link_clicks"] == "7"
    assert rec["profile_clicks"] == "2"


class FakeTimelineClient(FakeMetricsClient):
    def __init__(self, data=None, me="999", timeline=None):
        super().__init__(data or {})
        self.me = me
        self.timeline = timeline or []

    def get_me(self):
        return self.me

    def get_user_tweets(self, user_id, max_pages=2):
        return self.timeline


def _scheduled(tmp_path, name, body="本文サンプル", thread=False):
    p = tmp_path / name
    fm = textwrap.dedent(f"""\
        ---
        status: 予約済み
        scheduled_at: "2026-06-22T12:00:00+09:00"
        category: 技術ログ
        thread: {str(thread).lower()}
        posted_at:
        tweet_ids: []
        ---
        # 投稿文
        """)
    p.write_text(fm + body + "\n", encoding="utf-8")  # 複数行bodyはdedentを壊すため後結合
    return p


def test_reconcile_writes_back_tweet_ids_and_collects_metrics(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeTimelineClient(
        data={"200": {"public_metrics": {"impression_count": 300, "like_count": 5}}},
        timeline=[{"id": "200", "text": "本文サンプル", "created_at": "2026-06-22T03:00:00.000Z"}],
    )
    rows = fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    post = postfile.parse_post(path)
    assert post.status == postfile.STATUS_POSTED
    assert post.tweet_ids == ["200"]
    assert post.posted_at == "2026-06-22T12:00:00+09:00"  # 03:00 UTC -> 12:00 JST
    assert len(rows) == 1
    with csv_path.open(encoding="utf-8") as f:
        rec = list(csv.DictReader(f))[0]
    assert rec["tweet_id"] == "200"
    assert rec["posted_weekday"] == "月"  # 2026-06-22 is Monday
    assert rec["posted_hour"] == "12"


def test_reconcile_leaves_unposted_scheduled_untouched(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeTimelineClient(timeline=[])  # まだ投稿時刻が来ていない
    rows = fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    assert rows == []
    post = postfile.parse_post(path)
    assert post.status == "予約済み"
    assert post.tweet_ids == []


def test_reconcile_ignores_replies_to_others(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md")
    client = FakeTimelineClient(
        me="999",
        timeline=[{"id": "300", "text": "本文サンプル", "created_at": "2026-06-22T03:00:00.000Z",
                   "in_reply_to_user_id": "123"}],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.status == "予約済み"


def test_reconcile_matches_own_thread_reply(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md", body="1本目\n===\n2本目", thread=True)
    client = FakeTimelineClient(
        me="999",
        timeline=[
            {"id": "400", "text": "1本目", "created_at": "2026-06-22T03:00:00.000Z"},
            {"id": "401", "text": "2本目", "created_at": "2026-06-22T03:00:05.000Z",
             "in_reply_to_user_id": "999"},
        ],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.status == postfile.STATUS_POSTED
    assert post.tweet_ids == ["400", "401"]


def test_reconcile_thread_requires_all_tweets_matched(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md", body="1本目\n===\n2本目", thread=True)
    client = FakeTimelineClient(
        timeline=[{"id": "400", "text": "1本目", "created_at": "2026-06-22T03:00:00.000Z"}],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.status == "予約済み"  # 全ツイート揃うまで書き戻さない


def test_reconcile_matches_when_linebreaks_added_at_post_time(tmp_path):
    # X純正スケジューラ予約時に画面上で改行を足して投稿したケース（実運用で発生）
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md", body="一行で書いた本文。続きの文。")
    client = FakeTimelineClient(
        timeline=[{"id": "600", "text": "一行で書いた本文。\n\n続きの文。",
                   "created_at": "2026-06-22T03:00:00.000Z"}],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.tweet_ids == ["600"]


def test_reconcile_matches_when_punctuation_edited_at_post_time(tmp_path):
    # 手動投稿時に「。→改行」「箇条書きの・追加」等の手直しが入ったケース（実運用で確認）
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md", body="黄金律はDB=UTC・処理=UTC・API=ISO8601。表示だけ変換。")
    client = FakeTimelineClient(
        timeline=[{"id": "700", "text": "黄金律は\n・DB=UTC\n・処理=UTC\nAPI=ISO8601\n表示だけ変換。",
                   "created_at": "2026-06-22T03:00:00.000Z"}],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.tweet_ids == ["700"]


def test_reconcile_matches_despite_tco_links_and_html_escape(tmp_path):
    from xtools import postfile
    path = _scheduled(tmp_path, "a.md", body="設計の参考リンク https://example.com/long/path と Q&A")
    client = FakeTimelineClient(
        timeline=[{"id": "500", "text": "設計の参考リンク https://t.co/xyz と Q&amp;A",
                   "created_at": "2026-06-22T03:00:00.000Z"}],
    )
    fetch_metrics.fetch(now=datetime(2026, 6, 28, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=tmp_path / "m.csv")
    post = postfile.parse_post(path)
    assert post.tweet_ids == ["500"]


def test_fetch_malformed_posted_at_does_not_crash(tmp_path):
    import textwrap
    p = tmp_path / "bad.md"
    p.write_text(textwrap.dedent("""\
        ---
        status: 投稿済み
        thread: false
        posted_at: "not-a-date"
        tweet_ids: ["100"]
        ---
        # 投稿文
        本文
        """), encoding="utf-8")
    csv_path = tmp_path / "metrics_log.csv"
    client = FakeMetricsClient({"100": {"public_metrics": {"impression_count": 7}}})
    rows = fetch_metrics.fetch(now=datetime(2026, 6, 21, 12, 0, tzinfo=JST), client=client, post_dir=tmp_path, csv_path=csv_path)
    assert len(rows) == 1
    with csv_path.open(encoding="utf-8") as f:
        rec = list(csv.DictReader(f))[0]
    assert rec["posted_weekday"] == ""
    assert rec["impressions"] == "7"
