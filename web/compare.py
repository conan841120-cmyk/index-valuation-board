# -*- coding: utf-8 -*-
"""生成「作者原文截图（上）vs 我们的看板（下）」的并排对比图。

用法：
    python3 web/compare.py --shots-dir /tmp --article-dir data/reference/article_images
"""

import argparse
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 指数 → 作者 2026-09-27 日更文章中的配图序号
ARTICLE_MAP = {
    "nasdaq100": ("14", "纳斯达克100"),
    "sp500": ("12", "标普500"),
    "dividend_low_vol": ("05", "红利低波"),
    "csi_a500": ("19", "中证A500"),
    "csi_dividend": ("08", "中证红利"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots-dir", default=os.path.join(ROOT, "data", "reference", "v1_screenshots"))
    ap.add_argument("--article-dir", default=os.path.join(ROOT, "data", "reference", "article_images"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "outputs", "数据核对图（v1复刻版）"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    made = []
    for key, (num, name) in ARTICLE_MAP.items():
        art = os.path.join(args.article_dir, "%s.png" % num)
        ours = os.path.join(args.shots_dir, "our_%s.png" % key)
        if not (os.path.exists(art) and os.path.exists(ours)):
            print("跳过 %s（缺文件）" % key)
            continue
        a = Image.open(art).convert("RGB")
        b = Image.open(ours).convert("RGB")
        W = max(a.width, b.width)
        H = a.height + b.height + 16
        canvas = Image.new("RGB", (W, H), "#888888")
        canvas.paste(a.crop((0, 0, min(a.width, W), a.height)), (0, 0))
        canvas.paste(b.crop((0, 0, min(b.width, W), b.height)), (0, a.height + 16))
        out = os.path.join(args.out_dir, "%s_对比.png" % name)
        canvas.save(out)
        made.append(out)
        print("生成 %s（上：作者原文 / 下：v1 数据复刻版）" % out)
    print("共 %d 张" % len(made))
    return made


if __name__ == "__main__":
    main()
