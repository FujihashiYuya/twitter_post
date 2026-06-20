# X投稿自動化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承認済みの投稿を設定時刻に自動投稿し、週次で指標を取得・分析して改善提案を出す仕組みを、Claude routines（クラウド）＋GitHubで構築する。

**Architecture:** 決定論的処理（投稿・指標取得）は Python パッケージ `xtools/` に固定し誤投稿を防ぐ。クラウドの Claude routines がGitHubリポジトリをcloneしてスクリプトを実行し、結果を書き戻す。週次分析の「考察・レポート執筆」はroutine内のClaudeが担当する。

**Tech Stack:** Python 3.11+、`requests` + `requests-oauthlib`（OAuth 1.0a）、`PyYAML`、`pytest`。Claude routines（cron）、GitHub（プライベート）。

> **コミット規約:** 本計画で作成する各コミットのメッセージ末尾には必ず `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` を付与する。以下のステップでは簡潔のため本文のみ記載。

> **参照spec:** `docs/superpowers/specs/2026-06-17-x-post-automation-design.md`

---

## フェーズ構成と依存

1. **Phase 0** プロジェクト雛形（git/依存/設定）— 手動＋scaffolding
2. **Phase 1** `postfile.py`（md解析・検証・due判定）— TDD
3. **Phase 2** `auth.py` + `xclient.py`（認証・API）— TDD
4. **Phase 3** `gitio.py`（commit/push）— TDD
5. **Phase 4** `post_tweet.py`（投稿オーケストレーション）— TDD
6. **Phase 5** `fetch_metrics.py`（指標取得→CSV）— TDD
7. **Phase 6** X開発者ポータル設定（OAuth1.0aトークン発行）— 手動
8. **Phase 7** routine A/B 設定 — 手動
9. **Phase 8** `create-x-post` スキル作成 — 調査＋執筆

Phase 1〜5はローカルで完結・テスト可能。Phase 6以降は実環境設定。

---

## Phase 0: プロジェクト雛形

### Task 0.1: Gitリポジトリ化と基本設定ファイル

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `xtools/__init__.py`（空ファイル）
- Create: `analysis/.gitkeep`（空ファイル）

- [ ] **Step 1: Gitリポジトリを初期化**

PowerShellでリポジトリルート（`C:\workspace\twitter_post`）にて:
```
git init
git branch -M main
```

- [ ] **Step 2: `.gitignore` を作成**

```gitignore
# secrets
.env
*.env
!.env.example

# python
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/

# os
Thumbs.db
.DS_Store
```

- [ ] **Step 3: `.env.example` を作成**（実値は入れない）

```dotenv
# X (Twitter) API OAuth 1.0a user-context credentials
X_API_KEY=your_consumer_api_key
X_API_SECRET=your_consumer_api_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_token_secret
# optional: override API base (default https://api.x.com/2)
# X_API_BASE=https://api.twitter.com/2
```

- [ ] **Step 4: `requirements.txt` / `requirements-dev.txt` を作成**

`requirements.txt`:
```
requests>=2.31
requests-oauthlib>=1.3
PyYAML>=6.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
```

- [ ] **Step 5: `pyproject.toml` を作成**（pytestのimportパス設定）

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 6: 空の `xtools/__init__.py` と `analysis/.gitkeep` を作成**

`xtools/__init__.py` は空でよい。`analysis/.gitkeep` も空。

- [ ] **Step 7: 仮想環境を作り依存をインストール**

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

- [ ] **Step 8: 初回コミット**

```
git add .
git commit -m "chore: scaffold project (gitignore, deps, env example)"
```

---

## Phase 1: `postfile.py` — md解析・検証・due判定

投稿mdファイルのfrontmatter/本文を解析し、文字数検証・投稿対象判定・書き戻しを行う純粋ロジック。

**Files:**
- Create: `xtools/postfile.py`
- Test: `tests/test_postfile.py`

### Task 1.1: 文字数カウント `weighted_length`

X仕様の重み付き文字数（日本語/絵文字=2、ASCII等=1）。上限280。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_postfile.py`

```python
from xtools.postfile import weighted_length, MAX_WEIGHTED_LEN


def test_weighted_length_ascii_is_one_each():
    assert weighted_length("a" * 280) == 280


def test_weighted_length_japanese_is_two_each():
    assert weighted_length("あ" * 140) == 280


def test_max_constant():
    assert MAX_WEIGHTED_LEN == 280
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: FAIL（`ImportError: cannot import name 'weighted_length'`）

- [ ] **Step 3: 最小実装** — `xtools/postfile.py`

```python
from __future__ import annotations

MAX_WEIGHTED_LEN = 280


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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```
git add xtools/postfile.py tests/test_postfile.py
git commit -m "feat(postfile): add weighted_length char counter"
```

### Task 1.2: frontmatter解析とツイート抽出

- [ ] **Step 1: 失敗するテストを追記** — `tests/test_postfile.py`

```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: FAIL（`parse_post` 未定義）

- [ ] **Step 3: 実装を追記** — `xtools/postfile.py`

```python
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

STATUS_DRAFT = "下書き"
STATUS_APPROVED = "承認済み"
STATUS_POSTED = "投稿済み"
STATUS_REJECTED = "却下"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_THREAD_SEP_RE = re.compile(r"(?m)^={3,}\s*$")
_META_HEADING_RE = re.compile(r"(?m)^##\s+メタ情報.*")
_TITLE_HEADING_RE = re.compile(r"(?m)^#\s+投稿文\s*$")
_HR_RE = re.compile(r"(?m)^-{3,}\s*$")


@dataclass
class PostFile:
    path: Path
    status: str
    scheduled_at: datetime | None
    category: str | None
    thread: bool
    posted_at: str | None
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
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```
git add xtools/postfile.py tests/test_postfile.py
git commit -m "feat(postfile): parse frontmatter and split thread tweets"
```

### Task 1.3: due判定・文字数超過検出・frontmatter書き戻し

- [ ] **Step 1: 失敗するテストを追記** — `tests/test_postfile.py`

```python
from datetime import datetime, timezone, timedelta
from xtools.postfile import (
    is_due, find_due_posts, overlength_tweets, update_frontmatter,
    parse_post, STATUS_POSTED,
)

JST = timezone(timedelta(hours=9))


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
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: FAIL（`is_due` 等が未定義）

- [ ] **Step 3: 実装を追記** — `xtools/postfile.py`

```python
def is_due(post: PostFile, now: datetime) -> bool:
    return (
        post.status == STATUS_APPROVED
        and post.scheduled_at is not None
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
    return [
        (i, weighted_length(t))
        for i, t in enumerate(post.tweets)
        if weighted_length(t) > MAX_WEIGHTED_LEN
    ]


def update_frontmatter(path, **updates) -> None:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"No frontmatter to update in {path}")
    fm = yaml.safe_load(m.group(1)) or {}
    fm.update(updates)
    new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(f"---\n{new_fm}---\n{m.group(2)}", encoding="utf-8")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_postfile.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: コミット**

```
git add xtools/postfile.py tests/test_postfile.py
git commit -m "feat(postfile): add due check, overlength detection, frontmatter update"
```

---

## Phase 2: `auth.py` + `xclient.py` — 認証とX API

### Task 2.1: OAuth 1.0a 署名セッション `auth.py`

**Files:**
- Create: `xtools/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_auth.py`

```python
import pytest
from xtools.auth import make_session, MissingCredentialsError


def test_make_session_raises_when_missing(monkeypatch):
    for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(MissingCredentialsError):
        make_session()


def test_make_session_builds_oauth1(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "k")
    monkeypatch.setenv("X_API_SECRET", "s")
    monkeypatch.setenv("X_ACCESS_TOKEN", "t")
    monkeypatch.setenv("X_ACCESS_TOKEN_SECRET", "ts")
    session = make_session()
    # OAuth1Session exposes the consumer key on its auth object
    assert session.auth.client.client_key == "k"
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL（`make_session` 未定義）

- [ ] **Step 3: 実装** — `xtools/auth.py`

```python
import os

from requests_oauthlib import OAuth1Session


class MissingCredentialsError(RuntimeError):
    pass


_REQUIRED = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]


def make_session() -> OAuth1Session:
    vals = {k: os.environ.get(k) for k in _REQUIRED}
    missing = [k for k, v in vals.items() if not v]
    if missing:
        raise MissingCredentialsError(f"Missing env vars: {', '.join(missing)}")
    return OAuth1Session(
        client_key=vals["X_API_KEY"],
        client_secret=vals["X_API_SECRET"],
        resource_owner_key=vals["X_ACCESS_TOKEN"],
        resource_owner_secret=vals["X_ACCESS_TOKEN_SECRET"],
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```
git add xtools/auth.py tests/test_auth.py
git commit -m "feat(auth): OAuth1.0a session factory with credential check"
```

### Task 2.2: X APIクライアント `xclient.py`

投稿（スレッド対応）と指標取得。HTTPセッションは注入可能にしテストでfake化する。

**Files:**
- Create: `xtools/xclient.py`
- Test: `tests/test_xclient.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_xclient.py`

```python
import pytest
from xtools.xclient import XClient, XAPIError


class FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def post(self, url, json=None, timeout=None):
        self.requests.append(("POST", url, json))
        return self._responses.pop(0)

    def get(self, url, params=None, timeout=None):
        self.requests.append(("GET", url, params))
        return self._responses.pop(0)


def test_create_tweet_returns_id():
    s = FakeSession([FakeResp(201, {"data": {"id": "100"}})])
    client = XClient(s, base="https://api.x.com/2")
    assert client.create_tweet("hello") == "100"
    assert s.requests[0][1] == "https://api.x.com/2/tweets"
    assert s.requests[0][2] == {"text": "hello"}


def test_post_thread_chains_replies():
    s = FakeSession([
        FakeResp(201, {"data": {"id": "100"}}),
        FakeResp(201, {"data": {"id": "101"}}),
    ])
    client = XClient(s, base="https://api.x.com/2")
    ids = client.post_thread(["one", "two"])
    assert ids == ["100", "101"]
    # second tweet replies to the first
    assert s.requests[1][2] == {"text": "two", "reply": {"in_reply_to_tweet_id": "100"}}


def test_create_tweet_raises_on_error():
    s = FakeSession([FakeResp(403, text="forbidden")])
    client = XClient(s, base="https://api.x.com/2")
    with pytest.raises(XAPIError):
        client.create_tweet("hello")


def test_get_metrics_maps_by_id():
    s = FakeSession([FakeResp(200, {"data": [
        {"id": "100", "public_metrics": {"impression_count": 500, "like_count": 10}},
    ]})])
    client = XClient(s, base="https://api.x.com/2")
    result = client.get_metrics(["100"])
    assert result["100"]["public_metrics"]["impression_count"] == 500
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_xclient.py -v`
Expected: FAIL（`XClient` 未定義）

- [ ] **Step 3: 実装** — `xtools/xclient.py`

```python
import os

DEFAULT_BASE = os.environ.get("X_API_BASE", "https://api.x.com/2")


class XAPIError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(f"X API error {status}: {body}")
        self.status = status
        self.body = body


class XClient:
    def __init__(self, session, base: str | None = None):
        self.session = session
        self.base = (base or DEFAULT_BASE).rstrip("/")

    def create_tweet(self, text: str, in_reply_to: str | None = None) -> str:
        payload = {"text": text}
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        resp = self.session.post(f"{self.base}/tweets", json=payload, timeout=30)
        if resp.status_code != 201:
            raise XAPIError(resp.status_code, resp.text)
        return resp.json()["data"]["id"]

    def post_thread(self, tweets: list[str]) -> list[str]:
        ids: list[str] = []
        reply_to = None
        for text in tweets:
            tid = self.create_tweet(text, in_reply_to=reply_to)
            ids.append(tid)
            reply_to = tid
        return ids

    def get_metrics(self, tweet_ids: list[str]) -> dict:
        fields = "public_metrics,non_public_metrics,created_at"
        results: dict = {}
        for i in range(0, len(tweet_ids), 100):
            batch = tweet_ids[i : i + 100]
            resp = self.session.get(
                f"{self.base}/tweets",
                params={"ids": ",".join(batch), "tweet.fields": fields},
                timeout=30,
            )
            if resp.status_code != 200:
                raise XAPIError(resp.status_code, resp.text)
            for item in resp.json().get("data", []):
                results[item["id"]] = item
        return results
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_xclient.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```
git add xtools/xclient.py tests/test_xclient.py
git commit -m "feat(xclient): create tweet, post thread, fetch metrics"
```

---

## Phase 3: `gitio.py` — commit/push

副作用（git操作）を1ユニットに隔離。

**Files:**
- Create: `xtools/gitio.py`
- Test: `tests/test_gitio.py`

### Task 3.1: `commit_and_push`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_gitio.py`

```python
import subprocess
from xtools import gitio


def test_commit_and_push_invokes_git(monkeypatch):
    calls = []

    def fake_run(args, cwd=None, check=False):
        calls.append(args)
        # simulate "there are staged changes" for the diff --cached check
        class R:
            returncode = 1
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    pushed = gitio.commit_and_push(["a.md", "b.json"], "msg", cwd="/repo")
    assert pushed is True
    assert calls[0][:2] == ["git", "add"]
    assert any(c[:2] == ["git", "commit"] for c in calls)
    assert any(c == ["git", "push"] for c in calls)


def test_commit_and_push_noop_when_nothing_staged(monkeypatch):
    calls = []

    def fake_run(args, cwd=None, check=False):
        calls.append(args)
        class R:
            # diff --cached --quiet returns 0 => nothing staged
            returncode = 0 if args[:3] == ["git", "diff", "--cached"] else 1
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    pushed = gitio.commit_and_push(["a.md"], "msg", cwd="/repo")
    assert pushed is False
    assert not any(c == ["git", "push"] for c in calls)
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_gitio.py -v`
Expected: FAIL（`gitio` 未定義）

- [ ] **Step 3: 実装** — `xtools/gitio.py`

```python
import subprocess


def commit_and_push(paths: list[str], message: str, cwd: str | None = None, push: bool = True) -> bool:
    subprocess.run(["git", "add", *paths], cwd=cwd, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd)
    if staged.returncode == 0:
        return False  # nothing to commit
    subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True)
    if push:
        subprocess.run(["git", "push"], cwd=cwd, check=True)
    return True
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_gitio.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```
git add xtools/gitio.py tests/test_gitio.py
git commit -m "feat(gitio): commit_and_push helper with no-op guard"
```

---

## Phase 4: `post_tweet.py` — 投稿オーケストレーション

due判定 → 台帳チェック（二重投稿防止）→ 文字数検証 → 投稿 → 台帳/frontmatter更新 → commit/push。投稿成功ごとにcommit/pushして冪等性を高める。

**Files:**
- Create: `xtools/post_tweet.py`
- Test: `tests/test_post_tweet.py`

### Task 4.1: `post_due` コアロジック

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_post_tweet.py`

```python
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
    # second run: file status is 投稿済み AND ledger has it -> not posted again
    second_client = FakeClient()
    results = post_tweet.post_due(now=now, client=second_client, post_dir=tmp_path, ledger_path=ledger, do_git=False)
    assert second_client.calls == []
    assert results == []  # no due posts remain


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
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_post_tweet.py -v`
Expected: FAIL（`post_tweet` 未定義）

- [ ] **Step 3: 実装** — `xtools/post_tweet.py`

```python
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
    # exit non-zero if any error so the routine surfaces it
    if any(s.startswith("error") for _, s, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_post_tweet.py -v`
Expected: PASS

- [ ] **Step 5: dry-run のCLI動作を手動確認**

サンプル承認済みmdを1つ用意し:
```
python -m xtools.post_tweet --due-now --dry-run --now 2026-06-20T09:00:00+09:00 --no-git
```
Expected: `<file>: dry-run []` が表示され、APIを叩かない。

- [ ] **Step 6: コミット**

```
git add xtools/post_tweet.py tests/test_post_tweet.py
git commit -m "feat(post_tweet): orchestrate due posting with ledger idempotency"
```

---

## Phase 5: `fetch_metrics.py` — 指標取得→CSV

**Files:**
- Create: `xtools/fetch_metrics.py`
- Test: `tests/test_fetch_metrics.py`

### Task 5.1: 投稿済み収集とCSV追記

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_fetch_metrics.py`

```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `python -m pytest tests/test_fetch_metrics.py -v`
Expected: FAIL（`fetch_metrics` 未定義）

- [ ] **Step 3: 実装** — `xtools/fetch_metrics.py`

```python
import argparse
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path

from xtools import postfile
from xtools.auth import make_session
from xtools.xclient import XClient

JST = timezone(timedelta(hours=9))
REPO_ROOT = Path(__file__).resolve().parent.parent
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
    posted_dt = postfile._parse_dt(post.posted_at)
    weekday = WEEKDAYS[posted_dt.weekday()] if posted_dt else ""
    hour = posted_dt.astimezone(JST).hour if posted_dt else ""
    excerpt = (post.tweets[0][:30] if post.tweets else "").replace("\n", " ")
    return {
        "collected_at": collected_at,
        "tweet_id": tweet_id,
        "file": post.path.name,
        "posted_at": post.posted_at or "",
        "posted_weekday": weekday,
        "posted_hour": hour,
        "category": post.category or "",
        "impressions": pub.get("impression_count", ""),
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
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def fetch(now=None, client=None, post_dir=POST_DIR, csv_path=CSV_PATH, dry_run=False):
    now = now or datetime.now(JST)
    collected_at = now.isoformat()
    id_to_post = {}
    all_ids = []
    for post in collect_posted(post_dir):
        for tid in post.tweet_ids:
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_fetch_metrics.py -v`
Expected: PASS

- [ ] **Step 5: 全テスト実行**

Run: `python -m pytest -v`
Expected: 全PASS

- [ ] **Step 6: コミット**

```
git add xtools/fetch_metrics.py tests/test_fetch_metrics.py
git commit -m "feat(fetch_metrics): collect metrics into time-series CSV"
```

---

## Phase 6: X開発者ポータル設定（手動）

> このフェーズはコードではなく外部設定。各ステップ完了後にチェック。

### Task 6.1: アプリ作成とOAuth1.0aトークン発行

- [ ] **Step 1:** [X Developer Portal](https://developer.x.com/) でDeveloperアカウントを取得（無料枠廃止のため、サインアップ時に**従量課金（pay-per-use）**へ進む）。
- [ ] **Step 2:** 支払い方法（カード）を登録しクレジット購入。請求は投稿$0.015/件（URL含む$0.20/件）・読取$0.005/件・自分データ読取$0.001/件の従量。
- [ ] **Step 3:** **Project を作成 → その配下に App を作成**（v2投稿はProject必須。未所属だと403）。
- [ ] **Step 4:** App → Settings → User authentication settings で:
  - **OAuth 1.0a を ON**、**App permissions = Read and write**（既定のReadだと投稿が403）
  - Callback URI / Website URL は必須項目だが、**自己トークン発行では未使用**（ドメイン取得・ngrok不要）。Callback例 `http://localhost:3000/callback`、Website例 自分のXプロフィール等の実在https URL。
- [ ] **Step 5:** Keys and tokens タブで以下を発行・控える（**生成時のみ表示**）:
  - API Key / API Secret（= Consumer Keys）
  - Access Token / Access Token Secret（**自分のアカウント用**・長期有効・失効/更新なし）
  - ⚠️ 権限を Read and write にした**後**で Access Token を**再生成**（権限変更前のトークンはread-onlyのまま→投稿403）
- [ ] **Step 6:** ローカルで疎通確認。PowerShellで環境変数を設定し、最小投稿（テキスト1件$0.015）で確認:
  ```
  $env:X_API_KEY="..."; $env:X_API_SECRET="..."; $env:X_ACCESS_TOKEN="..."; $env:X_ACCESS_TOKEN_SECRET="..."
  python -c "from xtools.auth import make_session; from xtools.xclient import XClient; print(XClient(make_session()).create_tweet('テスト投稿（自動化疎通確認）'))"
  ```
  Expected: tweet idが表示され、実際に投稿される。確認後その投稿は手動削除してよい。

> 注: routineでは環境変数を直接設定するため `.env` ファイルは不要。ローカル検証で `.env` を使いたい場合のみ `python-dotenv` を追加してもよい（その場合も `.env` は `.gitignore` 済みでコミットしない）。

---

## Phase 7: Claude routines 設定（手動）

> 前提: Phase 0〜5 完了済みのリポジトリを **GitHubプライベートリポジトリ** にpush済みであること。さらに CLI で `/web-setup` を実行し、claude.ai に GitHub を接続しておく（routine がリポジトリを clone できるようにするため）。

### Task 7.1: GitHubへpush

- [ ] **Step 1:** GitHubでプライベートリポジトリを作成（例: `twitter_post`）。
- [ ] **Step 2:** リモート登録してpush:
  ```
  git remote add origin https://github.com/<your-account>/twitter_post.git
  git push -u origin main
  ```
- [ ] **Step 3:** `.env` がpushされていないことを確認（`git ls-files | Select-String env` で `.env.example` のみ表示されること）。

### Task 7.2: routine A（毎日の投稿）

- [ ] **Step 1:** [claude.ai/code/routines](https://claude.ai/code/routines) の「New routine」で作成し、対象リポジトリに上記GitHubリポジトリを指定。
- [ ] **Step 1b（重要）:** 当該リポジトリで **「Allow unrestricted branch pushes（既存ブランチへのpush許可）」を有効化**。routineは既定では `claude/` 始まりのブランチにしかpushできず、本設計の main への書き戻し（投稿済みステータス・分析レポート）が反映されないため必須。
- [ ] **Step 2:** スケジュール: cron `0 9,12,15,18,20,22 * * *` / timezone `Asia/Tokyo`。Webプリセット（毎時/毎日/毎週）にこの6時刻パターンは無いので、作成後に CLI で **`/schedule update`** してcron式を設定（端末がJSTなら現地時刻=JSTで適用）。
- [ ] **Step 3:** 環境変数（routine環境）に登録: `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET`。
- [ ] **Step 4:** 許可ドメインに `api.x.com` と `api.twitter.com` を追加。
- [ ] **Step 5:** セットアップコマンド: `pip install -r requirements.txt`。
- [ ] **Step 6:** プロンプトを以下に設定:
  > リポジトリルートで `python -m xtools.post_tweet --due-now` を実行せよ。このスクリプトは承認済みかつ投稿時刻が到来した投稿のみをXに投稿し、ファイル更新・台帳更新・commit・pushまで自身で行う。実行後、投稿/スキップ/失敗の結果を1〜2行で要約せよ。スクリプトが非ゼロ終了した場合はエラー内容を報告し、**手動で投稿し直さないこと**。
- [ ] **Step 7:** one-off実行（routine詳細の「Run now」）で疎通確認（承認済み&dueの投稿が無ければ "No due posts." となること）。問題なければスケジュール有効化。
  > 注: Max plan の routine 実行上限は 1日15回。routine A は6回/日でこの範囲内（残りは手動テスト等に使える）。

### Task 7.3: routine B（週次分析）

- [ ] **Step 1:** 同リポジトリで2本目のroutineを作成。
- [ ] **Step 2:** スケジュール: cron `0 12 * * 0` / timezone `Asia/Tokyo`（毎週日曜12:00）。
- [ ] **Step 3:** 環境変数・許可ドメイン・セットアップコマンドは routine A と同じ。
- [ ] **Step 4:** プロンプトを以下に設定:
  > 1) リポジトリルートで `python -m xtools.fetch_metrics` を実行し、今週の指標スナップショットを `analysis/metrics_log.csv` に追記せよ。
  > 2) `analysis/metrics_log.csv` と `account.md`、`CLAUDE.md` を読み込め。
  > 3) `analysis/<YYYY>-W<WW>_report.md`（ISO週番号）を、specのテンプレートに従って作成せよ: サマリ／投稿別パフォーマンス／時間帯×曜日別パフォーマンス／考察／来週の改善提案。改善提案は account.md の目標（フォロワー・平均インプレッション）と NG ルール（CLAUDE.md）に整合させること。投稿時間の実験結果（どの曜日・時刻が伸びたか）を必ず含めよ。
  > 4) 生成したレポートと更新CSVを git add → commit → push せよ。
- [ ] **Step 5:** one-off実行で疎通確認（CSVが追記され、レポートが生成・pushされること）。問題なければ有効化。

---

## Phase 8: `create-x-post` スキル作成

投稿「作成」ワークフローのスキル化。既存ベストプラクティスを調査の上、Claude Codeスキル形式で作成する。

**Files:**
- Create: `.claude/skills/create-x-post/SKILL.md`

### Task 8.1: 既存スキル/ベストプラクティス調査

- [ ] **Step 1:** WebSearch/WebFetchで以下を調査し、要点をメモする:
  - 公開されている Claude Code / Agent Skills のうち「SNS投稿」「コンテンツ作成」系の構成例
  - Anthropic公式のskill作成ベストプラクティス（`superpowers:writing-skills` の指針 + 公式skillリポジトリ）
  - 調査クエリ例: "Claude Code agent skill social media post", "anthropic skills SKILL.md best practices", "claude skill content creation workflow"
- [ ] **Step 2:** `superpowers:writing-skills` スキルを起動し、skill作成の作法（frontmatterのname/description、トリガ記述、簡潔さ）に従う。

### Task 8.2: SKILL.md 執筆

- [ ] **Step 1:** `.claude/skills/create-x-post/SKILL.md` を作成:

```markdown
---
name: create-x-post
description: Use when drafting a new X (Twitter) post for the @FujihashiYuya account — guides theme selection, fact-checking, rule-compliant drafting, the review checklist, and saving to post/ with the automation frontmatter (status/scheduled_at).
---

# X投稿作成ワークフロー

@FujihashiYuya 向けの投稿を、アカウント方針に沿って作成し `post/` に保存する。
投稿・指標取得は `xtools/` のスクリプトと routine が担うため、このスキルは**作成までを担当**する。

## 手順

1. **方針確認**: `account.md`（ターゲット読者・コンテンツ比率・NGルール・文体）と `CLAUDE.md`（チェックリスト）を参照する。
2. **テーマ決定**: 過去投稿（`post/*.md`）と重複しないテーマを選ぶ。コンテンツ比率（技術ログ40%/学習30%/ツール20%/個人開発10%）を意識する。
3. **裏取り**: 技術的事実・最新トレンドは必要に応じ WebSearch で確認する。
4. **下書き作成**: 文体方針（誠実・実直、提案型、押しつけない）に従う。1ツイート=重み付き280以下（日本語で約140字）。スレッドは本文を `===` 行で区切り `thread: true`。
5. **レビューチェックリスト適用**（CLAUDE.md より）:
   - 実体験ベース／技術的気づきがあるか
   - 会社名・クライアント・守秘・政治宗教・断定/マウント表現が無いか
   - 文字数・改行・ハッシュタグ（最大2）・絵文字控えめ
6. **保存**: `post/YYYYMMDD_連番_テーマ.md` に以下のfrontmatter付きで保存する。`status: 下書き`、`scheduled_at` は投稿候補時刻（9/12/15/18/20/22時 JST）から、曜日・時刻を過去分とばらして提案する（投稿時間の実験）。

## 保存フォーマット

\`\`\`markdown
---
status: 下書き
scheduled_at: "YYYY-MM-DDThh:00:00+09:00"
category: 技術ログ
thread: false
posted_at:
tweet_ids: []
---

# 投稿文

[本文]

## メタ情報
- 作成日: YYYY-MM-DD
- カテゴリ: ...
- 文字数: XX
- ステータス: 下書き
\`\`\`

## 完了後

ユーザーに「レビューして、投稿するものは `status: 承認済み` に変更し push してください」と伝える（週まとめて事前承認）。
```

- [ ] **Step 2:** スキルが認識されるか確認（Claude Codeで `/create-x-post` 等で起動できること、もしくはSkillツール一覧に現れること）。
- [ ] **Step 3:** 試しに1件下書きを作成させ、frontmatterと文字数・チェックリストが満たされることを確認。

- [ ] **Step 4: コミット**

```
git add .claude/skills/create-x-post/SKILL.md
git commit -m "feat(skill): add create-x-post drafting workflow skill"
git push
```

---

## 完了確認（受け入れ基準・specより）

- [ ] 承認済み投稿が `scheduled_at` のスロットで自動投稿され、mdに `投稿済み`/`tweet_id` が記録される
- [ ] 同一投稿が二重投稿されない（台帳＋status）
- [ ] 週次で `metrics_log.csv` が更新され、`analysis/` に考察＋改善提案レポートが生成される
- [ ] `create-x-post` スキルでルール準拠の下書きが `status:下書き` で保存される
- [ ] 秘密情報がリポジトリにコミットされていない（`git ls-files` に `.env` が無い）
- [ ] `python -m pytest` が全PASS

---

## 既知のリスク / 運用上の注意

- **二重投稿の残余リスク**: 投稿成功後に commit/push が失敗すると、次回起動で再投稿の可能性。緩和: 投稿ごとに即commit/push＋台帳。発生時は週次レポートで重複を検知し手動対応。
- **non-public指標の30日制限**: 投稿後30日を超えるとクリック等は取得不可。週次取得で窓内に収める。
- **routine実行上限**: 1日6回＋週1回は通常の上限内だが、毎時起動に切替える場合は上限消費に注意。
- **文字数チェックの保守性**: URLは実際には23字換算だが本実装は文字通りカウント（安全側＝超過判定で投稿を止める）。長いURLを含む投稿が誤って弾かれたら本文を調整する。
