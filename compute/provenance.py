"""构建输入和计算代码的内容指纹，拒绝用旧看板验收新输入。"""

import hashlib
from pathlib import Path

from compute.config import ROOT


def _digest(root, paths):
    value = hashlib.sha256()
    for path in sorted(paths):
        value.update(str(path.relative_to(root)).encode("utf-8"))
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def input_digest(root=None):
    root = Path(root or ROOT)
    paths = [root / "data/series/raw_inputs.json", root / "data/reference/screenshots.json"]
    paths.extend((root / "data/official_snapshots").glob("*.csv"))
    return _digest(root, [p for p in paths if p.exists()])


def code_digest(root=None):
    root = Path(root or ROOT)
    paths = list((root / "compute").glob("*.py")) + list((root / "fetch").glob("*.py"))
    paths.extend(root / p for p in ["web/app.js", "web/render.py", "web/template.html", "tools/watch_rule.py"])
    return _digest(root, [p for p in paths if p.exists()])
