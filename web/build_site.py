"""三个入口统一打包；调用者负责刷新所需模块，其余模块使用已保存输入。"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web import render, us_market, sp500
from web.navigation import CSS as NAV_STYLE, navigation


def build(out):
    out = Path(out)
    render.build(str(out / 'index.html'))
    us_market.build(ROOT / 'data/us_market', out / 'us-market')
    sp500.build(ROOT / 'data/us_market/sp500.json', out / 'sp500-deviation')
    # 仅完整站点增加导航，保留原单文件估值页面的离线阅读行为。
    index = out / 'index.html'
    nav = '<div style="max-width:1440px;margin:auto;padding:16px 32px 0"><style>' + NAV_STYLE + '</style>' + navigation('valuation') + '</div>'
    index.write_text(index.read_text(encoding='utf-8').replace('<body>', '<body>' + nav), encoding='utf-8')
    (out / '.nojekyll').touch()
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'docs')
    build(parser.parse_args().out)
