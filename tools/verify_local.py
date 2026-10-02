# -*- coding: utf-8 -*-
"""离线验收：重建当前输入 → 报告 → 页面 → 全部测试；任一步失败立即停止。"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="outputs/估值看板.html", help="本地 HTML 输出路径")
    args = parser.parse_args()
    steps = [
        [sys.executable, "compute/run_all.py", "--rebuild"],
        [sys.executable, "compute/report.py"],
        [sys.executable, "macro/hsi/update.py"],
        [sys.executable, "web/render.py", "--out", args.out],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        ["node", "tests/test_frontend_logic.js"],
        ["node", "tests/test_macro_frontend.js"],
    ]
    for command in steps:
        subprocess.run(command, cwd=ROOT, check=True)
    print("离线重建、报告、渲染与测试完成：%s" % args.out)


if __name__ == "__main__":
    main()
