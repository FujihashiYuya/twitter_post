import argparse
import csv
from datetime import datetime
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


def _row(post, tweet_id, metric, collected_at):
    pub = metric.get("public_metrics", {})
    nonpub = metric.get("non_public_metrics", {})
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
        "impressions": nonpub.get("impression_count", pub.get("impression_count", "")),
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
    id_to_post = {}
    all_ids = []
    for post in collect_posted(post_dir):
        for tid in post.tweet_ids:
            if tid in id_to_post:
                continue  # dedupe: a tweet_id seen in an earlier file wins
            id_to_post[tid] = post
            all_ids.append(tid)
    if not all_ids or dry_run:
        return []
    if client is None:
        client = XClient(make_session())
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
