# -*- coding: utf-8 -*-
"""口径变化监控：每天盯作者日更图里「每个指数用的是哪个估值口径」，与项目配置比对。

背景：作者 2026-09-23 给「红利低波」用的是市净率LF，2026-09-27 又改成了股息率——
口径变了但我们不知道，就会拿错指标做判断。本模块自动发现当天文章并核对口径。

发现文章：公众号「合集」接口（mp/appmsgalbum）无需登录，返回该合集下最近的文章标题与链接。
识别口径：图里工具栏第 1 行被选中的指标按钮是从头到尾填满蓝色的（#4EABC4），
         按蓝色色块的水平位置即可判定选中的是哪一个指标（不需要 OCR）。
识别指数：对图顶部一行（指数名 + 代码 + 点位 + 涨跌幅）做 OCR，优先用指数代码匹配。

用法：
    python3 tools/watch_rule.py                     # 抓当天最新日更文章并核对
    python3 tools/watch_rule.py --images-dir DIR    # 离线模式：对本地图片目录核对
    python3 tools/watch_rule.py --url <文章链接>
输出：data/watch/rule_check.json + 控制台摘要；有口径不一致时退出码为 2。
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute.config import DATA, INDICES  # noqa: E402
from fetch.common import fetch, get_json, save_raw  # noqa: E402

ALBUM = {"biz": "Mzk2NDA3Mzk2NA==", "album_id": "3843200297499312129"}
DAILY_TITLE = re.compile(r"【\d{4}-\d{2}-\d{2}】.*核心指数估值")
WATCH_DIR = os.path.join(DATA, "watch")

# 指标按钮标定（文章配图为 2x 截图，工具栏第 1 行 y≈14~52）
BUTTON_ROW = (14, 52)
BUTTONS = [
    ("市盈率TTM", 777),
    ("市净率LF", 977),
    ("股息率", 1128),
    ("风险溢价", 1262),
    ("市销率TTM", 1438),
    ("市现率TTM", 1660),
]
RANGE_ROW = [("3Y", 300, 345), ("5Y", 348, 390), ("10Y", 300, 386), ("上市以来", 400, 500)]
BLUE = (78, 171, 196)          # 选中态填充色 #4EABC4
BLUE_TOL = 26


# ----------------------------------------------------------------- 发现文章

def latest_daily_article(count=20):
    """从公众号合集接口取最新一篇日更估值文章。返回 {title, url, date} 或 None。"""
    url = ("https://mp.weixin.qq.com/mp/appmsgalbum?action=getalbum&__biz=%s"
           "&album_id=%s&f=json&count=%d" % (ALBUM["biz"].replace("=", "%3D"), ALBUM["album_id"], count))
    data = get_json(url, referer="https://mp.weixin.qq.com/")
    save_raw("watch_album.json", data)
    arts = ((data.get("getalbum_resp") or {}).get("article_list")) or []
    for a in arts:
        title = (a.get("title") or "").strip()
        if DAILY_TITLE.search(title):
            return {
                "title": title,
                "url": (a.get("url") or "").replace("\\x26amp;", "&").replace("&amp;", "&"),
                "date": datetime.datetime.fromtimestamp(int(a.get("create_time") or 0)).strftime("%Y-%m-%d"),
                "ts": int(a.get("create_time") or 0),
            }
    return None


def article_image_urls(article_url):
    """抓文章页，按出现顺序取出内容配图的 cdn_url（宽 > 500 才算内容图）。"""
    resp = fetch(article_url)
    html = resp.content.decode("utf-8", "ignore")
    entries = []
    for m in re.finditer(r"cdn_url:\s*'([^']+)'(.{0,400}?)height:\s*'(\d+)'", html, re.S):
        url, mid = m.group(1), m.group(2)
        wm = re.search(r"width:\s*'(\d+)'", mid)
        width = int(wm.group(1)) if wm else 0
        if "mmbiz" not in url:
            continue
        url = url.replace("\\x26amp;", "&").replace("&amp;", "&")
        if width > 500:
            entries.append({"url": url, "width": width, "height": int(m.group(3))})
    # 去重（同一张图可能被引用两次），保留顺序
    seen, out = set(), []
    for e in entries:
        if e["url"] in seen:
            continue
        seen.add(e["url"])
        out.append(e)
    return out


# ----------------------------------------------------------------- 图像识别

def _np():
    import numpy as np
    return np


def blue_runs(image_path):
    """返回工具栏第 1 行里蓝色实心块的 [(x0, x1, center)]。"""
    np = _np()
    from PIL import Image
    a = np.asarray(Image.open(image_path).convert("RGB")).astype(int)
    y0, y1 = BUTTON_ROW
    strip = a[y0:y1, :, :]
    mask = ((abs(strip[:, :, 0] - BLUE[0]) < BLUE_TOL) &
            (abs(strip[:, :, 1] - BLUE[1]) < BLUE_TOL) &
            (abs(strip[:, :, 2] - BLUE[2]) < BLUE_TOL))
    colsum = mask.sum(axis=0)
    runs, start = [], None
    for x, v in enumerate(colsum):
        if v > 0 and start is None:
            start = x
        elif v == 0 and start is not None:
            if x - start > 100:
                runs.append((start, x, (start + x) // 2))
            start = None
    if start is not None and len(colsum) - start > 100:
        runs.append((start, len(colsum), (start + len(colsum)) // 2))
    return runs


def detect_metric(image_path):
    """判定图中被选中的指标（与作者图一致：选中的按钮整块填蓝）。"""
    runs = [r for r in blue_runs(image_path) if r[0] > 520]      # 排除左侧"时间范围"
    if not runs:
        return None, None
    x0, x1, cx = max(runs, key=lambda r: r[1] - r[0])
    best = min(BUTTONS, key=lambda b: abs(b[1] - cx))
    return best[0], {"x": [x0, x1], "center": cx, "confidence": abs(best[1] - cx)}


def ocr(image_path, crop, lang="chi_sim+eng", psm="7"):
    """裁剪后调用 tesseract（macOS: /opt/homebrew/bin/tesseract；Linux: tesseract）。"""
    exe = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    if not os.path.exists(exe):
        return ""
    from PIL import Image
    tmp = os.path.join(tempfile.gettempdir(), "watch_ocr.png")
    Image.open(image_path).convert("RGB").crop(crop).save(tmp)
    try:
        r = subprocess.run([exe, tmp, "stdout", "-l", lang, "--psm", psm],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def detect_index(image_path):
    """OCR 图顶部一行（指数名 + 代码 + 点位 + 涨跌幅），优先用代码匹配到本项目指数。"""
    text = ocr(image_path, (0, 140, 1500, 230))
    hit = None
    for cfg in INDICES:
        code = cfg["code"]
        if code and code.replace(".", "") in text.replace(".", "").replace(" ", ""):
            hit = cfg
            break
    if not hit:
        for cfg in INDICES:
            if cfg["name"] in text.replace(" ", ""):
                hit = cfg
                break
    return (hit["key"] if hit else None), text


# ----------------------------------------------------------------- 核对与报告

# 口径键 → 作者图上的按钮文字
METRIC_LABEL = {"pe": "市盈率TTM", "pb": "市净率LF", "dy": "股息率", "rp": "风险溢价",
                "ps": "市销率TTM", "pcf": "市现率TTM"}


def summarize_result(w):
    """统一监控状态：五个唯一指数均成功识别才算完整。"""
    expected_keys = [cfg["key"] for cfg in INDICES]
    rows = w.get("rows") or []
    covered_keys = []
    for key in expected_keys:
        hits = [r for r in rows if r.get("index_key") == key]
        if len(hits) == 1 and isinstance(hits[0].get("match"), bool) and hits[0].get("author_metric"):
            covered_keys.append(key)
    missing = [key for key in expected_keys if key not in covered_keys]
    mismatched = max(sum(1 for r in rows if r.get("index_key") in expected_keys and
                         r.get("match") is False), w.get("mismatched") or 0)
    if w.get("state") == "failed":
        state = "failed"
    elif mismatched:
        state = "mismatch"
    elif missing:
        state = "incomplete"
    else:
        state = "consistent"
    return {"state": state, "coverage": len(covered_keys), "covered": len(covered_keys),
            "expected": len(expected_keys), "missing": missing,
            "matched": sum(1 for key in covered_keys if next(r for r in rows if r.get("index_key") == key).get("match") is True),
            "mismatched": mismatched}


def check_images(images, article=None):
    """images: [(路径, 来源描述)]。返回核对结果 dict。"""
    rows, mismatches = [], []
    for path, src in images:
        key, header = detect_index(path)
        metric, meta = detect_metric(path)
        cfg = next((c for c in INDICES if c["key"] == key), None)
        our_label = METRIC_LABEL.get(cfg["metric"]) if cfg else None
        row = {
            "image": os.path.basename(path),
            "source": src,
            "ocr_header": header,
            "index_key": key,
            "index_name": cfg["name"] if cfg else None,
            "author_metric": metric,
            "our_metric": cfg["metric"] if cfg else None,
            "our_metric_label": our_label,
            "match": None,
            "detected": bool(cfg and metric),
        }
        if cfg and metric:
            row["match"] = (our_label == metric)
        rows.append(row)
        if row["match"] is False:
            mismatches.append(row)
    result = {
        "checked_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
        "article": article,
        "images": len(rows),
        "matched": sum(1 for r in rows if r["match"] is True),
        "mismatched": len(mismatches),
        "rows": rows,
    }
    result.update(summarize_result(result))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="指定文章链接（默认自动取合集里最新一篇日更）")
    ap.add_argument("--images-dir", help="离线模式：直接核对本地图片目录")
    ap.add_argument("--keep-images", action="store_true", help="把当天配图留档到 data/watch/images/")
    args = ap.parse_args()

    os.makedirs(WATCH_DIR, exist_ok=True)
    result_path = os.path.join(WATCH_DIR, "rule_check.json")
    previous = None
    if os.path.exists(result_path):
        try:
            with open(result_path, encoding="utf-8") as fh:
                previous = json.load(fh)
        except (OSError, ValueError):
            pass
    images, article = [], None
    try:
        if args.images_dir:
            for name in sorted(os.listdir(args.images_dir)):
                if name.lower().endswith((".png", ".jpg", ".jpeg")):
                    images.append((os.path.join(args.images_dir, name), "本地图片"))
            article = {"title": "(离线模式)", "url": None, "date": None}
        else:
            url = args.url
            if not url:
                found = latest_daily_article()
                if not found:
                    raise RuntimeError("未在合集里找到日更估值文章")
                article, url = found, found["url"]
                print("发现文章：%s（%s）" % (article["title"], article["date"]))
            else:
                article = {"title": "(指定文章)", "url": url, "date": None}
            entries = article_image_urls(url)
            print("配图 %d 张" % len(entries))
            img_dir = os.path.join(WATCH_DIR, "images")
            os.makedirs(img_dir, exist_ok=True)
            for k, e in enumerate(entries, 1):
                path = os.path.join(img_dir, "%02d.png" % k)
                with open(path, "wb") as fh:
                    fh.write(fetch(e["url"].replace("http://", "https://"),
                                   referer="https://mp.weixin.qq.com/").content)
                images.append((path, "文章配图 %d" % k))
        result = check_images(images, article)
    except Exception as exc:  # noqa: BLE001
        result = {"checked_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
                  "article": article, "images": len(images), "rows": [],
                  "state": "failed", "detail": str(exc)}
        print("口径核对失败：%s" % exc)
    result.update(summarize_result(result))
    if result["state"] in ("failed", "incomplete") and previous:
        # 避免连续失败嵌套累积；保留最后有结论的检查供页面提示。
        result["previous_result"] = previous.get("previous_result") or previous
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    print("\n%-10s %-10s %-10s %s" % ("指数", "作者口径", "本项目", "结论"))
    for r in result["rows"]:
        if not r["index_key"]:
            continue
        flag = "✅ 一致" if r["match"] else ("❌ 不一致" if r["match"] is False else "— 未识别")
        print("%-10s %-10s %-10s %s" % (r["index_name"], r["author_metric"] or "未识别",
                                        r["our_metric_label"] or r["our_metric"], flag))
    print("\n覆盖 %d/%d 个唯一指数；口径不一致 %d 处；状态 %s" %
          (result["coverage"], result["expected"], result["mismatched"], result["state"]))
    if not args.keep_images and not args.images_dir:
        for path, _ in images:
            try:
                os.remove(path)
            except OSError:
                pass
    return {"consistent": 0, "mismatch": 2, "incomplete": 1, "failed": 1}[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
