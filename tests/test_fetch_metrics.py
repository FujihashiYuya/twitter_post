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
