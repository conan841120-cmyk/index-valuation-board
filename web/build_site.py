"""三个入口统一打包；调用者负责刷新所需模块，其余模块使用已保存输入。"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web import render, us_market


def build(out):
    out = Path(out)
    render.build(str(out / 'index.html'))
    us_market.build(ROOT / 'data/us_market', out / 'us-market')
    # 仅完整站点增加导航，保留原单文件估值页面的离线阅读行为。
    index = out / 'index.html'
    navigation = '<nav aria-label="站点导航" style="max-width:1440px;margin:auto;padding:12px 32px 0"><a href="us-market/">美股信息日报与预警 →</a></nav>'
    index.write_text(index.read_text(encoding='utf-8').replace('<body>', '<body>' + navigation), encoding='utf-8')
    (out / '.nojekyll').touch()
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'docs')
    build(parser.parse_args().out)
