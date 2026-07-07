"""Xプロフィールのヘッダー画像(1500x500)を生成する。

使い方: python tools/make_header.py
出力: assets/header_dark.png / assets/header_light.png

X表示の注意: 端末により上下端が数十px切れ、プロフィール画面では左下にアイコンが
重なるため、文字はセンター寄り(セーフエリア: 中央1200x300)に収める。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1500, 500
OUT = Path(__file__).resolve().parent.parent / "assets"

L1 = "実務 × 個人開発の Webエンジニア"
L2 = "設計・フロント・AWSインフラ、ときどきAI実装"
L3 = "学びと「なぜそう作ったか」を毎日メモ"

FONT_BOLD = "C:/Windows/Fonts/YuGothB.ttc"
FONT_MED = "C:/Windows/Fonts/YuGothM.ttc"

VARIANTS = {
    "dark": {"bg": "#0F172A", "l1": "#F8FAFC", "sub": "#94A3B8", "accent": "#3B82F6"},
    "light": {"bg": "#FAFAF8", "l1": "#1F2328", "sub": "#57606A", "accent": "#0969DA"},
}


def make(name, c):
    img = Image.new("RGB", (W, H), c["bg"])
    d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(FONT_BOLD, 62)
    f2 = ImageFont.truetype(FONT_MED, 34)

    cx = W // 2
    d.text((cx, 185), L1, font=f1, fill=c["l1"], anchor="mm")
    # アクセントの区切り線
    d.rectangle([cx - 40, 243, cx + 40, 247], fill=c["accent"])
    d.text((cx, 300), L2, font=f2, fill=c["sub"], anchor="mm")
    d.text((cx, 356), L3, font=f2, fill=c["sub"], anchor="mm")

    OUT.mkdir(exist_ok=True)
    path = OUT / f"header_{name}.png"
    img.save(path)
    return path


if __name__ == "__main__":
    for name, colors in VARIANTS.items():
        print(make(name, colors))
