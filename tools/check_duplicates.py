"""下書き投稿がアカウントの過去投稿と重複していないかを、あいまい一致で検査する。

使い方:
    python tools/check_duplicates.py            # 下書き・承認済みを全チェック
    python tools/check_duplicates.py 0.5        # 閾値を変える（既定0.6）

背景（2026-07-21の実話）: 完全一致の突合では「フロントエンド→フロント」「DB設計→RDB設計」
程度の微修正投稿を8本すり抜けた。SequenceMatcherの類似度で拾うこと。
要 .env（X API読み取り）。
"""
import sys
import difflib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xtools import postfile
from xtools.fetch_metrics import _match_key
from xtools.auth import make_session
from xtools.xclient import XClient

THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
CHECK_STATUSES = (postfile.STATUS_DRAFT, postfile.STATUS_APPROVED)


def main():
    client = XClient(make_session())
    timeline = client.get_user_tweets(client.get_me(), max_pages=3)
    tl = [(t["id"], t.get("created_at", "")[:10], _match_key(t.get("text", ""))) for t in timeline]
    print(f"timeline: {len(tl)} tweets / threshold: {THRESHOLD}")

    flagged = 0
    for p in sorted(Path(__file__).resolve().parent.parent.glob("post/*.md")):
        post = postfile.parse_post(p)
        if post.status not in CHECK_STATUSES or not post.tweets:
            continue
        key = _match_key(post.tweets[0])
        best = max(tl, key=lambda t: difflib.SequenceMatcher(None, key, t[2]).ratio())
        ratio = difflib.SequenceMatcher(None, key, best[2]).ratio()
        if ratio >= THRESHOLD:
            flagged += 1
            print(f"\nDUPLICATE? {ratio:.2f} {p.name}")
            print(f"  posted {best[1]} id={best[0]}: {best[2][:70]}")
    print(f"\n{'NG: ' + str(flagged) + '件の重複疑い' if flagged else 'OK: 重複疑いなし'}")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
