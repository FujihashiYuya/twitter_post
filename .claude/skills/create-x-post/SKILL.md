---
name: create-x-post
description: Drafts a new X (Twitter) post for the @FujihashiYuya account and saves it to post/ with automation frontmatter. Use when the user wants to write, draft, or create a new X post — even if they just say "投稿を作って", "ツイートを書いて", or "X用の文を作りたい". Guides theme selection, WebSearch fact-checking, rule-compliant drafting, checklist review, and saving as status 下書き so xtools/ automation can post it after approval.
---

# X投稿作成ワークフロー

@FujihashiYuya 向けの投稿を、アカウント方針に沿って作成し `post/` に保存する。投稿・指標取得は `xtools/` のスクリプトと Claude routine が担うため、このスキルは**作成までを担当**する（投稿はしない）。

## 手順

1. **方針確認**: `account.html`（ターゲット読者・コンテンツ比率・NGルール・文体）と `CLAUDE.md`（投稿レビューチェックリスト）を参照する。

2. **テーマ決定**: `post/*.md` の過去投稿と重複しないテーマを選ぶ。コンテンツ比率（技術ログ40% / 学習習慣30% / ツール活用20% / 個人開発10%）を意識する。**下書き完成後に必ず `python tools/check_duplicates.py` であいまい一致の重複検査を通す**（完全一致では「一語の言い換え投稿」をすり抜けた実績あり。類似度0.6以上が出たら書き直すか却下）。

3. **裏取り**: 技術的事実・最新トレンドは必要に応じて WebSearch で確認する。

4. **下書き作成**: 文体方針（誠実・実直、提案型、押しつけない）に従う。**1行目は勝ちパターンの型で書く**（W27-29実測。①逆説・誤解訂正「〜だと思っていたが違った」②構造化・数え上げ「〜は3本柱」③法則の言い切り「〜は足し算」。抽象論・定石紹介の書き出しは実測で下位）。1ツイートは重み付き280以下（日本語で約140字）。スレッドは本文を `===`（行頭のイコール3つ以上のみの行）で区切り、frontmatter を `thread: true` にする。**週1本はスレッド（5〜10ツイート・保存される型）を含める**。**リンクを載せる場合は本文(1ツイート目)に入れず、`thread: true` にして2ツイート目（=最初の返信）に置く**（本文リンクはリーチ激減＋API$0.20）。

5. **レビューチェックリスト適用**（`CLAUDE.md` のチェックリストに従う）:
   - 実体験ベース／技術的気づきが含まれるか
   - 会社名・クライアント・守秘義務・政治宗教に触れていないか
   - 断定／マウント表現がないか
   - 文字数・改行・ハッシュタグ最大2・絵文字控えめか

6. **投稿時刻の提案**: `scheduled_at` は候補時刻（JST）`09 / 12 / 15 / 18 / 20 / 22` 時から選ぶ。**配置ルール（W27-29実測）: 週で一番強い球（スレッド・逆説型）→月9時、2番手→平日12時、金20時以降は使わない、土日は昼〜夕方に軽め・問いかけ型**。それ以外の枠は `analysis/metrics_log.csv` を見て過去分と意図的にばらす（時間帯実験の継続）。

7. **保存**: `post/YYYYMMDD_連番_テーマ.md` に下記フォーマットで `status: 下書き` として保存する。

## 保存フォーマット

````markdown
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
- カテゴリ: [技術ログ / 学習習慣 / ツール活用 / 個人開発]
- 文字数: XX
- ステータス: 下書き
````

## 完了後

ユーザーに「内容をレビューし、投稿するものは frontmatter の `status` を `承認済み` に変更して push してください（週まとめて事前承認）」と伝える。
