# 恒生指数领先指标：云端更新模块

用户于2026-10-02确认本项目采用 `observation_period / quarter_end_carry_forward` 和 `explicit_unbiased`。这是生产计算口径的确定，不代表已取得原作者源码。

季度末3、6、9、12月更新最近两个已结束季度的名义GDP之和，并沿用到下一次更新。四因子分别按36个月半衰期、显式无偏加权方差标准化，再各乘0.25。信用脉冲固定为 `(SF6[t] - SF6[t-12]) / GDP2Q[t]` 的过去3个月均值。所有作者锁定参数由代码检查。

`python update.py` 离线重算；`python update.py --refresh` 联网获取统计局官方社零同比、官方出厂价格同比指数、当季名义GDP、人民银行社融增量、金管局总额M2直接同比，以及恒指月末收盘价。源文件缓存至 `data/raw/`，处理后历史留在 `data/processed/`。每个数据集单独校验单位、覆盖和重复值；失败回滚到原处理后文件，并在网页标出沿用缓存。原始响应缓存由GitHub Actions保存，不提交进公开仓库。

金管局更新最近3个月公布材料；更早的逐月原始发布值保留。统计局与社融序列可能修订，当前历史不是完整历史数据版本。页面的经济观察期、公布日期、成功抓取时间和生成时间分别记录；不能把季度末的观察值视为当月已经可知。

单一日更工作流 `.github/workflows/daily.yml` 沿用已验收修复版的北京时间08:30名义时刻。抓取、计算、页面生成与回归检查成功后发布同一GitHub Pages页面。GitHub调度、排队和数据发布均可能滞后。

输出：`../../data/hsi_macro.json`（网页快照）、`data/processed/historical_replication.csv`（可核验月度数据）、`output/diagnostics/indicator_diagnostics.csv`（完整分解）。网页CSV导出保留空值，虚线仅连接已知端点，不填写缺失月值。

验证：本目录运行 `python -m pytest -q`；仓库根目录运行 `node tests/test_macro_frontend.js`。
