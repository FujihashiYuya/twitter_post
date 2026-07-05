"""運用ドキュメント(md)を閲覧用HTMLに変換する。

使い方:
    python tools/md2html.py account.md analysis/x_strategy.md analysis/reply_targets.md

出力は入力と同じ場所に同名の .html。md が正（skillsやCLAUDE.mdが参照する）で、
HTML は閲覧用の派生物。md を更新したら再実行して差し替える。
"""
import sys
from pathlib import Path

import markdown

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #f6f8fa; --card: #ffffff; --ink: #1f2328; --sub: #57606a;
    --accent: #0969da; --border: #d0d7de;
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Hiragino Sans", "Yu Gothic UI", "Meiryo", sans-serif;
         background: var(--bg); color: var(--ink); margin: 0; padding: 32px 16px; line-height: 1.75; }}
  .wrap {{ max-width: 900px; margin: 0 auto; background: var(--card);
          border: 1px solid var(--border); border-radius: 10px; padding: 32px 40px; }}
  h1 {{ font-size: 25px; border-bottom: 2px solid var(--accent); padding-bottom: 8px; }}
  h2 {{ font-size: 19px; border-left: 5px solid var(--accent); padding-left: 10px; margin-top: 36px; }}
  h3 {{ font-size: 16px; margin-top: 26px; color: var(--accent); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin: 12px 0; }}
  th, td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; vertical-align: top; }}
  th {{ background: #eef2f6; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  code {{ background: #eef2f6; border-radius: 4px; padding: 1px 6px; font-size: 13px;
         font-family: Consolas, monospace; }}
  pre {{ background: #eef2f6; border-radius: 8px; padding: 12px 16px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  blockquote {{ border-left: 4px solid var(--accent); margin: 12px 0; padding: 4px 16px;
               background: #f0f7ff; color: var(--ink); border-radius: 0 8px 8px 0; }}
  hr {{ border: none; border-top: 1px solid var(--border); margin: 28px 0; }}
  a {{ color: var(--accent); }}
  .src {{ color: var(--sub); font-size: 12px; margin-top: 32px; border-top: 1px solid var(--border);
         padding-top: 10px; }}
</style>
</head>
<body>
<div class="wrap">
{body}
<div class="src">source: {src}（このHTMLは派生物。更新は md 側で行い <code>python tools/md2html.py</code> で再生成）</div>
</div>
</body>
</html>
"""


def convert(md_path: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    first_line = next((l for l in text.splitlines() if l.startswith("# ")), md_path.stem)
    title = first_line.lstrip("# ").strip()
    out = md_path.with_suffix(".html")
    out.write_text(TEMPLATE.format(title=title, body=body, src=md_path.as_posix()), encoding="utf-8")
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(convert(Path(arg)))
