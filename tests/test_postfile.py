from xtools.postfile import weighted_length, MAX_WEIGHTED_LEN


def test_weighted_length_ascii_is_one_each():
    assert weighted_length("a" * 280) == 280


def test_weighted_length_japanese_is_two_each():
    assert weighted_length("あ" * 140) == 280


def test_max_constant():
    assert MAX_WEIGHTED_LEN == 280


import textwrap
from xtools.postfile import parse_post, STATUS_APPROVED


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


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
