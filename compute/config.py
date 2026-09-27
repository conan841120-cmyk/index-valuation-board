# -*- coding: utf-8 -*-
"""指数估值看板 —— 口径与数据源配置（唯一需要人工维护的"业务规则"文件）。

口径说明（来自作者 2026-09-27 日更文章的正文规则）：
  "部分指数看市盈率，部分是看市净率（已经帮大家做了筛选），中证全指是看风险溢价（越高越好），
   中证红利是看股息率（越高越好），这两个数据是蓝色线在上，红色在下，和其他图不同。"

修正记录：
  2026-09-23 文章中「红利低波」用的是 市净率LF，作者在 2026-09-27 的日更图中已改为「股息率」。
  本配置以 09-27 的口径为准（PB 对红利指数不是合理的"便宜度"信号）。
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
SERIES = os.path.join(DATA, "series")
SNAPSHOTS = os.path.join(DATA, "official_snapshots")
REFERENCE = os.path.join(DATA, "reference")
OUTPUTS = os.path.join(ROOT, "outputs")
DASHBOARD_JSON = os.path.join(DATA, "dashboard.json")

# ---------------------------------------------------------------- 统计口径

# 时间范围（年）。ALL = 上市以来 / 数据起点
WINDOWS = [("3Y", 3), ("5Y", 5), ("10Y", 10), ("ALL", None)]
DEFAULT_WINDOW = "10Y"

# 分位位置：危险值 = 80 分位、中位数 = 50 分位、机会值 = 20 分位
# （反向指标：股息率 / 风险溢价 的高低判断相反 → 危险值取 20 分位、机会值取 80 分位）
PCT_HIGH = 0.80
PCT_MEDIAN = 0.50
PCT_LOW = 0.20

# 区间提示缓冲带（用于"接近/进入"危险区间的措辞，不做单点触发）
BUFFER_NEAR = 0.78
BUFFER_IN = 0.82

# 股息率推导方法：full_return（全收益法） | pe_anchored（PE 锚定倒数法） | blend（两者几何平均）
YIELD_METHOD = "blend"

# 股息率近端衰减校准窗口（天）。修正幅度从末点的 k_end 线性衰减到窗口外的 1.0。
# 实测（对照作者 2026-09-27 截图）：1825 天时 红利低波 分位点偏差 −6.1pp（硬锚定为 −14.5pp），
# 危险值/中位数/机会值偏差 ≤3%；这是拟合参数，作者口径若有变化需重新校准。
YIELD_CALIBRATION_DAYS = 1825

# ---------------------------------------------------------------- 回归容差

# 与作者截图的比对容差（阈值类=危险值/机会值/中位数）
TOLERANCES = {
    # 真实序列（蛋卷 PE、中证官方 PE）
    "real": {"threshold_pct": 2.0, "current_pct": 2.0, "zscore_abs": 0.15, "percentile_pp": 5.0,
             "level_pct": 0.5},
    # 推导序列（股息率历史）：当前值必须等于官方真实值；阈值放宽并只做提示；分位点仅记录
    "derived": {"current_abs": 0.03, "threshold_pct": 5.0, "zscore_abs": 0.25,
                "percentile_pp": None},
    # 真实区间不足（中证A500）：只检查真实区间与字段完整性
    "partial": {"threshold_pct": None, "current_pct": None},
}

# 各指数的数据可信等级（决定用哪套容差）
QUALITY = {
    "nasdaq100": "real",
    "sp500": "real",
    "dividend_low_vol": "derived",
    "csi_a500": "partial",
    "csi_dividend": "derived",
}

# 危险值/机会值的相对不确定度（用于在页面上画"误差带"，避免把阈值当硬线）
# 实测依据：真实序列阈值偏差 ≤2%；股息率推导序列阈值偏差 ≤5%（且区间收窄 11~14%）
THRESHOLD_UNCERTAINTY = {"real": 0.02, "derived": 0.05, "partial": None}

# ---------------------------------------------------------------- 指标定义

METRICS = {
    "pe": {"key": "pe", "label": "市盈率TTM", "digits": 2, "unit": ""},
    "pb": {"key": "pb", "label": "市净率LF", "digits": 2, "unit": ""},
    "dy": {"key": "dy", "label": "股息率", "digits": 2, "unit": "%"},
    "rp": {"key": "rp", "label": "风险溢价", "digits": 2, "unit": "%"},
}

# 反向指标：数值越高越"便宜"
INVERSE_METRICS = {"dy", "rp"}

# ---------------------------------------------------------------- 指数表

INDICES = [
    {
        "key": "nasdaq100",
        "name": "纳斯达克100",
        "code": "NDX.GI",
        "metric": "pe",
        "sources": {"danjuan": "NDX", "tencent": "usNDX", "csindex": None},
        "level_source": "tencent",
        "rebalance": [],                 # 海外指数不做中证调仓标记
        "note": "作者口径：市盈率TTM",
    },
    {
        "key": "sp500",
        "name": "标普500",
        "code": "SPX.GI",
        "metric": "pe",
        "sources": {"danjuan": "SP500", "tencent": "us.INX", "csindex": None},
        "level_source": "tencent",
        "rebalance": [],
        "note": "作者口径：市盈率TTM",
    },
    {
        "key": "csi_a500",
        "name": "中证A500",
        "code": "000510.SH",
        "metric": "pe",
        "sources": {
            "danjuan": None,             # 蛋卷无该指数
            "tencent": None,
            "csindex": "000510",         # 官方 perf 自带每日 PE（自 2024-09-03 起）
        },
        "level_source": "csindex",
        "rebalance": "semiannual",       # 每年 6 月 / 12 月第二个星期五
        "note": "真实 PE 仅自 2024-09-03 起（499 个交易日）；更早无公开真实数据",
    },
    {
        "key": "dividend_low_vol",
        "name": "红利低波",
        "code": "H30269.CSI",
        "metric": "dy",
        "sources": {
            "danjuan": "CSIH30269",
            "tencent": None,
            "csindex": "H30269",
            "csindex_tr": "H20269",      # 中证红利低波动全收益指数（用于股息率推导）
        },
        "level_source": "csindex",
        "rebalance": "annual_dec",       # 每年 12 月第二个星期五
        "note": "作者 09-27 口径：股息率（09-23 那张的市净率LF 系作者选错，已作废）",
    },
    {
        "key": "csi_dividend",
        "name": "中证红利",
        "code": "000922.CSI",
        "metric": "dy",
        "sources": {
            "danjuan": "SH000922",
            "tencent": None,
            "csindex": "000922",
            "csindex_tr": "H00922",      # 中证红利全收益指数
        },
        "level_source": "csindex",
        "rebalance": "annual_dec",
        "note": "作者口径：股息率（越高越便宜）",
    },
]

INDEX_BY_KEY = {i["key"]: i for i in INDICES}


def metric_label(index):
    return METRICS[index["metric"]]["label"]


def is_inverse(index):
    return index["metric"] in INVERSE_METRICS
