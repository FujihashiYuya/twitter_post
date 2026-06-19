from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

MAX_WEIGHTED_LEN = 280

STATUS_DRAFT = "下書き"
STATUS_APPROVED = "承認済み"
STATUS_POSTED = "投稿済み"
STATUS_REJECTED = "却下"

JST = timezone(timedelta(hours=9))

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_THREAD_SEP_RE = re.compile(r"(?m)^={3,}\s*$")
_META_HEADING_RE = re.compile(r"(?m)^##\s+メタ情報.*")  # Sentinel that ends the tweet region. Assumes tweet text never starts a line with "## メタ情報".
_TITLE_HEADING_RE = re.compile(r"(?m)^#\s+投稿文\s*$")
_HR_RE = re.compile(r"(?m)^-{3,}\s*$")  # Strips Markdown horizontal rules (---) used as template separators. Note: a legitimate --- inside tweet content would also be stripped.


def weighted_length(text: str) -> int:
    total = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x0000 <= cp <= 0x10FF
            or 0x2000 <= cp <= 0x200D
            or 0x2010 <= cp <= 0x201F
            or 0x2032 <= cp <= 0x2037
        ):
            total += 1
        else:
            total += 2
    return total


@dataclass
class PostFile:
    path: Path
    status: str
    scheduled_at: datetime | None
    category: str | None
    thread: bool
    posted_at: str | None  # Intentionally stored as a string: written once at post time, never compared in logic.
    tweet_ids: list[str]
    tweets: list[str]
    raw_frontmatter: dict


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    data = yaml.safe_load(m.group(1)) or {}
    return data, m.group(2)


def extract_tweet_region(body: str) -> str:
    m = _META_HEADING_RE.search(body)
    region = body[: m.start()] if m else body
    region = _TITLE_HEADING_RE.sub("", region, count=1)
    region = _HR_RE.sub("", region)
    return region


def split_tweets(region: str, thread: bool) -> list[str]:
    parts = _THREAD_SEP_RE.split(region) if thread else [region]
    return [p.strip() for p in parts if p.strip()]


def _parse_dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def parse_post(path) -> PostFile:
    path = Path(path)
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    thread = bool(fm.get("thread", False))
    return PostFile(
        path=path,
        status=fm.get("status", ""),
        scheduled_at=_parse_dt(fm.get("scheduled_at")),
        category=fm.get("category"),
        thread=thread,
        posted_at=fm.get("posted_at"),
        tweet_ids=list(fm.get("tweet_ids") or []),
        tweets=split_tweets(extract_tweet_region(body), thread),
        raw_frontmatter=fm,
    )


def is_due(post: PostFile, now: datetime) -> bool:
    if post.scheduled_at is None:
        return False
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    return (
        post.status == STATUS_APPROVED
        and post.scheduled_at <= now
        and not post.tweet_ids
    )


def find_due_posts(post_dir, now: datetime) -> list[PostFile]:
    due = []
    for path in sorted(Path(post_dir).glob("*.md")):
        post = parse_post(path)
        if is_due(post, now):
            due.append(post)
    return due


def overlength_tweets(post: PostFile) -> list[tuple[int, int]]:
    result = []
    for i, t in enumerate(post.tweets):
        wl = weighted_length(t)
        if wl > MAX_WEIGHTED_LEN:
            result.append((i, wl))
    return result


def update_frontmatter(path, **updates) -> None:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"No frontmatter to update in {path}")
    fm = yaml.safe_load(m.group(1)) or {}
    fm.update(updates)
    for k, v in list(fm.items()):
        if isinstance(v, datetime):
            fm[k] = v.isoformat()
    new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(f"---\n{new_fm}---\n{m.group(2)}", encoding="utf-8")
