import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from xtools import postfile
from xtools.auth import make_session
from xtools.xclient import XClient
from xtools.gitio import commit_and_push

JST = timezone(timedelta(hours=9))
REPO_ROOT = Path(__file__).resolve().parent.parent
POST_DIR = REPO_ROOT / "post"
LEDGER_PATH = REPO_ROOT / "analysis" / "posted_ledger.json"


def load_ledger(path) -> dict:
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_ledger(ledger: dict, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def post_due(
    now=None,
    client=None,
    post_dir=POST_DIR,
    ledger_path=LEDGER_PATH,
    dry_run=False,
    do_git=True,
):
    now = now or datetime.now(JST)
    ledger = load_ledger(ledger_path)
    results = []
    for post in postfile.find_due_posts(post_dir, now):
        name = post.path.name
        if name in ledger:
            results.append((name, "skip-ledger", ledger[name]["tweet_ids"]))
            continue
        over = postfile.overlength_tweets(post)
        if over:
            results.append((name, f"error-overlength {over}", []))
            continue
        if dry_run:
            results.append((name, "dry-run", []))
            continue
        if client is None:
            client = XClient(make_session())
        tweet_ids = client.post_thread(post.tweets)
        posted_at = now.isoformat()
        ledger[name] = {"tweet_ids": tweet_ids, "posted_at": posted_at}
        save_ledger(ledger, ledger_path)
        postfile.update_frontmatter(
            post.path,
            status=postfile.STATUS_POSTED,
            posted_at=posted_at,
            tweet_ids=tweet_ids,
        )
        if do_git:
            commit_and_push(
                [str(post.path), str(ledger_path)],
                f"chore: post {name} ({tweet_ids[0]})",
                cwd=str(REPO_ROOT),
            )
        results.append((name, "posted", tweet_ids))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post approved & due tweets to X")
    parser.add_argument("--due-now", action="store_true", help="post all approved & due posts")
    parser.add_argument("--dry-run", action="store_true", help="show actions without posting")
    parser.add_argument("--now", help="override current time (ISO8601), for testing")
    parser.add_argument("--no-git", action="store_true", help="do not commit/push")
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(JST)
    results = post_due(now=now, dry_run=args.dry_run, do_git=not args.no_git)

    if not results:
        print("No due posts.")
    for name, status, ids in results:
        print(f"{name}: {status} {ids}")
    if any(s.startswith("error") for _, s, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
