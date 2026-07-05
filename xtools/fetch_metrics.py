import argparse
import csv
import html
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from xtools import postfile
from xtools.auth import make_session
from xtools.postfile import JST
from xtools.xclient import XClient

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCERPT_MAX_CHARS = 30
POST_DIR = REPO_ROOT / "post"
CSV_PATH = REPO_ROOT / "analysis" / "metrics_log.csv"

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

CSV_COLUMNS = [
    "collected_at", "tweet_id", "file", "posted_at", "posted_weekday", "posted_hour",
    "category", "impressions", "likes", "retweets", "replies", "quotes", "bookmarks",
    "url_link_clicks", "profile_clicks", "text_excerpt",
]


def collect_posted(post_dir):
    items = []
    for path in sorted(Path(post_dir).glob("*.md")):
        post = postfile.parse_post(path)
        if post.status == postfile.STATUS_POSTED and post.tweet_ids:
            items.append(post)
    return items


def collect_scheduled(post_dir):
    """X純正スケジューラ予約分（予約済み・tweet_ids未記入）を集める。"""
    items = []
    for path in sorted(Path(post_dir).glob("*.md")):
        post = postfile.parse_post(path)
        if post.status == postfile.STATUS_SCHEDULED and not post.tweet_ids:
            items.append(post)
    return items


_URL_RE = re.compile(r"https?://\S+")


def _match_key(text: str) -> str:
    # API側はURLがt.co短縮・&等がHTMLエスケープで返り、手動投稿時は改行・句読点・記号の
    # 手直しも入る（実運用で確認）。文字(L)と数字(N)だけを残して比較する。
    # 本文は100文字超で内容が投稿ごとに異なるため、この正規化でも誤マッチは実質起きない。
    text = html.unescape(text)
    text = _URL_RE.sub("", text)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] in ("L", "N"))


def _to_jst_iso(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return created_at or ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST).isoformat()


def reconcile(client, post_dir=POST_DIR, scheduled=None):
    """X純正スケジューラで投稿された分の tweet_id をタイムラインから突合し、
    md の frontmatter に status/posted_at/tweet_ids を書き戻す。

    まだ投稿時刻が来ていない予約分はタイムラインに現れないだけなので、
    マッチしなかった投稿は「予約済み」のまま何もしない（正常系）。
    """
    scheduled = collect_scheduled(post_dir) if scheduled is None else scheduled
    if not scheduled:
        return []
    me = client.get_me()
    timeline = client.get_user_tweets(me)
    # 他人への返信は除外（自スレッドの2ツイート目以降は in_reply_to_user_id == 自分なので残る）
    own = [t for t in timeline if t.get("in_reply_to_user_id") in (None, me)]
    by_key = {}
    for t in own:
        by_key.setdefault(_match_key(t.get("text", "")), t)
    updated = []
    for post in scheduled:
        matched = [by_key.get(_match_key(text)) for text in post.tweets]
        if not matched or any(m is None for m in matched):
            continue  # 全ツイートが揃うまで書き戻さない（スレッド途中の取り違え防止）
        postfile.update_frontmatter(
            post.path,
            status=postfile.STATUS_POSTED,
            posted_at=_to_jst_iso(matched[0].get("created_at", "")),
            tweet_ids=[m["id"] for m in matched],
        )
        updated.append(post.path.name)
    return updated


def _row(post, tweet_id, metric, collected_at):
    pub = metric.get("public_metrics", {})
    nonpub = metric.get("non_public_metrics", {})
    # APIプランによっては non_public_metrics が「ゼロ埋めで返る」（実測）。
    # キー存在でのフォールバックでは 0 に潰されるため、両方のうち大きい方を採用する。
    imp = [v for v in (nonpub.get("impression_count"), pub.get("impression_count"))
           if isinstance(v, int)]
    try:
        posted_dt = postfile._parse_dt(post.posted_at)
    except ValueError:
        posted_dt = None
    if posted_dt is not None:
        posted_jst = posted_dt.astimezone(JST)
        weekday = WEEKDAYS[posted_jst.weekday()]
        hour = str(posted_jst.hour)
        posted_at_str = posted_dt.isoformat()
    else:
        weekday = ""
        hour = ""
        posted_at_str = post.posted_at if isinstance(post.posted_at, str) else ""
    excerpt = (post.tweets[0][:EXCERPT_MAX_CHARS] if post.tweets else "").replace("\n", " ")
    return {
        "collected_at": collected_at,
        "tweet_id": tweet_id,
        "file": post.path.name,
        "posted_at": posted_at_str,
        "posted_weekday": weekday,
        "posted_hour": hour,
        "category": post.category or "",
        "impressions": max(imp) if imp else "",
        "likes": pub.get("like_count", ""),
        "retweets": pub.get("retweet_count", ""),
        "replies": pub.get("reply_count", ""),
        "quotes": pub.get("quote_count", ""),
        "bookmarks": pub.get("bookmark_count", ""),
        "url_link_clicks": nonpub.get("url_link_clicks", ""),
        "profile_clicks": nonpub.get("user_profile_clicks", ""),
        "text_excerpt": excerpt,
    }


def append_rows(rows, csv_path):
    if not rows:
        return
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if f.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)


def fetch(now=None, client=None, post_dir=POST_DIR, csv_path=CSV_PATH, dry_run=False):
    now = now or datetime.now(JST)
    collected_at = now.isoformat()
    scheduled = collect_scheduled(post_dir)
    posted = collect_posted(post_dir)
    if dry_run or (not scheduled and not posted):
        return []
    if client is None:
        client = XClient(make_session())
    if scheduled and reconcile(client, post_dir, scheduled=scheduled):
        posted = collect_posted(post_dir)  # 書き戻し分を含めて読み直す
    id_to_post = {}
    all_ids = []
    for post in posted:
        for tid in post.tweet_ids:
            if tid in id_to_post:
                continue  # dedupe: a tweet_id seen in an earlier file wins
            id_to_post[tid] = post
            all_ids.append(tid)
    if not all_ids:
        return []
    metrics = client.get_metrics(all_ids)
    rows = [_row(id_to_post[tid], tid, metrics.get(tid, {}), collected_at) for tid in all_ids]
    append_rows(rows, csv_path)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch X metrics for posted tweets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    rows = fetch(dry_run=args.dry_run)
    print(f"Collected metrics for {len(rows)} tweets -> {CSV_PATH}")


if __name__ == "__main__":
    main()
