---
name: analyze-x-week
description: Generate the weekly X analytics report for @FujihashiYuya from analysis/metrics_log.csv. Use when the user wants the weekly review/analysis of their X posts — e.g. "今週のXの分析", "週次レポート作って", "投稿のパフォーマンスを見たい", "X analyze". Reads the metrics CSV + account.html and writes analysis/<YYYY>-W<WW>_report.md with findings and improvement ideas.
---

# X 週次分析レポート生成（オンデマンド）

`analysis/metrics_log.csv`（GitHub Actions の `fetch-metrics` が毎週収集）を読み、`account.html` の目標・KPIと照らして考察・改善提案を書く。**投稿時間の実験結果（時間帯×曜日）を必ず含める。**

## 手順
1. `analysis/metrics_log.csv` を読む。無い/空なら「まだ指標データがありません（投稿が貯まると `fetch-metrics` が収集します）」と伝えて終了。
2. 最新の収集分（`collected_at` が最大の週）を主対象に、過去スナップショットと比較。
3. `account.html`（目標・主要KPI・コンテンツ比率・NGルール）と `CLAUDE.md` を参照。
4. `analysis/<YYYY>-W<WW>_report.md`（ISO週番号）を次の構成で作成:
   - **サマリ**: 今週の投稿数 / 平均インプレッション / 平均エンゲージメント率 / 先週比
   - **投稿別パフォーマンス（上位・下位）**: 投稿｜カテゴリ｜曜日｜時刻｜imp｜いいね｜RT｜返信｜eng率
   - **時間帯×曜日 別パフォーマンス（投稿時間の実験集計）**: 曜日｜時刻｜サンプル数｜平均imp｜平均eng率 → 反応の良い時間帯の仮説を更新
   - **考察**: 何が伸びた/伸びなかったか・要因仮説
   - **来週の改善提案**: 主要KPI（プロフィール訪問→フォロー転換率・保存数・返信数）とNGルールに整合した、具体的な投稿テーマ・文体・投稿時間帯の調整案
5. フォロワー数だけでなく、保存数・返信数・転換率の観点で示唆を出す。

## 完了後
- 生成したレポートのパスを伝え、要点を3〜5行で要約。
- 記録に残す場合は `git add analysis/ && git commit && git push` を促す（このスキルは自動コミットしない）。
