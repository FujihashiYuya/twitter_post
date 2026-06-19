import textwrap
from datetime import datetime, timezone, timedelta

from xtools.postfile import (
    weighted_length,
    MAX_WEIGHTED_LEN,
    parse_post,
    is_due,
    find_due_posts,
    overlength_tweets,
    update_frontmatter,
    STATUS_APPROVED,
    STATUS_POSTED,
)

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# weighted_length
# ---------------------------------------------------------------------------

def test_weighted_length_ascii_is_one_each():
    assert weighted_length("a" * 280) == 280


def test_weighted_length_japanese_is_two_each():
    assert weighted_length("あ" * 140) == 280


def test_max_constant():
    assert MAX_WEIGHTED_LEN == 280


# ---------------------------------------------------------------------------
# parse_post / extract_tweet_region / split_tweets
# ---------------------------------------------------------------------------

def test_parse_single_tweet(tmp_path):
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        category: 技術ログ
        thread: false
        tweet_ids: []
        ---

        # 投稿文

        これはテスト投稿です。

        ---

        ## メタ情報
        - 作成日: 2026-06-17
        """)
    post = parse_post(p)
    assert post.status == STATUS_APPROVED
    assert post.category == "技術ログ"
    assert post.thread is False
    assert post.tweets == ["これはテスト投稿です。"]
    assert post.tweet_ids == []


def test_parse_thread_splits_on_equals(tmp_path):
    p = _write(tmp_path, "b.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T12:00:00+09:00"
        thread: true
        tweet_ids: []
        ---

        # 投稿文

        1本目のツイート

        ===

        2本目のツイート

        ## メタ情報
        """)
    post = parse_post(p)
    assert post.tweets == ["1本目のツイート", "2本目のツイート"]


def test_parse_legacy_file_without_frontmatter(tmp_path):
    p = _write(tmp_path, "legacy.md", """\
        # 投稿文

        昔の投稿
        """)
    post = parse_post(p)
    assert post.status == ""
    assert post.scheduled_at is None


def test_thread_true_no_separator_returns_single_element(tmp_path):
    """thread: true with NO === separator returns the whole body as a single-element tweets list."""
    p = _write(tmp_path, "c.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: true
        tweet_ids: []
        ---

        # 投稿文

        スレッドの唯一のツイート

        ## メタ情報
        """)
    post = parse_post(p)
    assert post.tweets == ["スレッドの唯一のツイート"]


# ---------------------------------------------------------------------------
# _parse_dt / is_due (FIX 1 + I3)
# ---------------------------------------------------------------------------

def test_is_due_true_when_approved_past_and_unposted(tmp_path):
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        本文
        """)
    post = parse_post(p)
    assert is_due(post, datetime(2026, 6, 20, 9, 0, tzinfo=JST)) is True
    assert is_due(post, datetime(2026, 6, 20, 8, 0, tzinfo=JST)) is False


def test_is_due_false_when_already_has_tweet_ids(tmp_path):
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: ["123"]
        ---
        # 投稿文
        本文
        """)
    post = parse_post(p)
    assert is_due(post, datetime(2026, 6, 21, 9, 0, tzinfo=JST)) is False


def test_is_due_naive_now_does_not_raise(tmp_path):
    """is_due with a tz-aware scheduled_at and a naive now does NOT raise."""
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        本文
        """)
    post = parse_post(p)
    # naive now — must not raise TypeError
    naive_past = datetime(2026, 6, 20, 9, 0)   # treated as JST → exactly on time → True
    naive_early = datetime(2026, 6, 20, 8, 0)  # naive earlier → False
    assert is_due(post, naive_past) is True
    assert is_due(post, naive_early) is False


def test_parse_dt_naive_scheduled_at_attached_jst(tmp_path):
    """A file with no-timezone scheduled_at is parsed to a tz-aware (JST) datetime and is_due works."""
    p = _write(tmp_path, "naive.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00"
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        本文
        """)
    post = parse_post(p)
    assert post.scheduled_at is not None
    assert post.scheduled_at.tzinfo is not None, "scheduled_at must be tz-aware after _parse_dt"
    assert post.scheduled_at.tzinfo == JST
    # tz-aware now comparison must work
    assert is_due(post, datetime(2026, 6, 20, 9, 0, tzinfo=JST)) is True
    assert is_due(post, datetime(2026, 6, 20, 8, 59, tzinfo=JST)) is False


# ---------------------------------------------------------------------------
# overlength_tweets (FIX 3)
# ---------------------------------------------------------------------------

def test_overlength_detects_too_long(tmp_path):
    p = _write(tmp_path, "a.md", f"""\
        ---
        status: 承認済み
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        {"あ" * 141}
        """)
    post = parse_post(p)
    assert overlength_tweets(post) == [(0, 282)]


# ---------------------------------------------------------------------------
# update_frontmatter (FIX 2)
# ---------------------------------------------------------------------------

def test_update_frontmatter_preserves_body(tmp_path):
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---

        # 投稿文

        本文はそのまま
        """)
    update_frontmatter(p, status=STATUS_POSTED, posted_at="2026-06-20T09:00:01+09:00", tweet_ids=["999"])
    reparsed = parse_post(p)
    assert reparsed.status == STATUS_POSTED
    assert reparsed.tweet_ids == ["999"]
    assert reparsed.tweets == ["本文はそのまま"]


def test_update_frontmatter_datetime_value_uses_iso_T_format(tmp_path):
    """update_frontmatter must write datetime values in ISO T format, not YAML space format."""
    p = _write(tmp_path, "a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---

        # 投稿文

        本文
        """)
    dt_value = datetime(2026, 6, 20, 9, 0, 1, tzinfo=JST)
    update_frontmatter(p, posted_at=dt_value)
    raw = p.read_text(encoding="utf-8")
    # Must NOT contain the YAML space-separated datetime format
    assert "2026-06-20 09:00:01" not in raw
    # Must contain ISO T format
    assert "2026-06-20T09:00:01" in raw


# ---------------------------------------------------------------------------
# find_due_posts (FIX 5)
# ---------------------------------------------------------------------------

def test_find_due_posts_returns_filename_sorted_order(tmp_path):
    """find_due_posts returns multiple simultaneously-due posts in filename-sorted order."""
    now = datetime(2026, 6, 21, 0, 0, tzinfo=JST)
    _write(tmp_path, "02_b.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        Bの投稿
        """)
    _write(tmp_path, "01_a.md", """\
        ---
        status: 承認済み
        scheduled_at: "2026-06-20T09:00:00+09:00"
        thread: false
        tweet_ids: []
        ---
        # 投稿文
        Aの投稿
        """)
    due = find_due_posts(tmp_path, now)
    assert len(due) == 2
    assert due[0].path.name == "01_a.md"
    assert due[1].path.name == "02_b.md"
