# 方向确认记录（direction-approved.md）

按 `huashu-design` Skill 的 **Gate 文件协议**，本文件记录三方向初稿的展示与用户选择原话。

## 展示情况

- 展示时间：2026-09-27
- 三方向初稿（均为真实数据、可交互、单文件 HTML）：

| 方向 | 逻辑 | 风格／参照 | 初稿文件 | 截图 |
| --- | --- | --- | --- | --- |
| A | 逻辑一 · 秒数轮盘（`date +%S`=37 → 37%20+1=**18**） | 深色画廊裱框 Gallery Dark（参照 Glass / 美术馆暗房） | `design/design-demos/A-gallery-dark.html` | `design/design-demos/shots/A-gallery-dark.png` |
| B | 逻辑二 · 现实参照（标杆迁移） | 财经数据新闻版面（参照 FT / Reuters 数据新闻） | `design/design-demos/B-editorial-data.html` | `design/design-demos/shots/B-editorial-data.png` |
| C | 逻辑三 · 最佳设计师 | Giorgia Lupi（Pentagram）· Data Humanism | `design/design-demos/C-data-humanism.html` | `design/design-demos/shots/C-data-humanism.png` |

- 三版骨架互异：A 一屏一图（暗房）／B 报刊刊头＋分栏 small multiples／C 纵向叙事＋估值尺。
- 一次性并排截图：`design/design-demos/shots/三方向对比.png`

## 用户选择（原话）

> **B**

## 后续动作

1. 按方向 B 重做主看板视觉：`web/template.html` + `web/app.js` → `outputs/估值看板.html`（沿用 `data/dashboard.json`，功能不减）。
2. 保留的功能清单：5 指数切换、3Y/5Y/10Y/上市以来、指标切换（主指标 / 真实 PE·PB 并排）、视图切换（指标/分位点/标准差）、统计与明细数据、移动平均、CSV 导出、自定义分位阈值、误差带、≈ 推导标注、中证A500 真实区间提示、调仓标志。
3. 落地后出对比截图，并复跑 `tests/` 回归（数据层未变，16 项应全绿）。

## B 版落地后的验收记录

- 落地完成：2026-09-27，`outputs/估值看板.html` 已切换为 B 方向视觉。
- 随后按用户反馈迭代三轮：
  1. 修正左侧估值轴量程（调仓标志曾挂在估值轴上，把左轴拉成点位量级）；
  2. 指数顺序调整为 纳斯达克100 → 标普500 → **中证A500** → 红利低波 → 中证红利；调仓三角统一贴底；
  3. 横轴改为 `YY-MM`（>4 年每半年、短窗口每季度），并修掉同名标签重复；中证A500 页脚区分「官方估值字段首日 2024-09-03」与「周频首点 2024-09-06」。
- **用户验收原话（2026-09-27）：「排版已经完全没有问题了」** → 视觉方向 B 定稿，不再改动字体、配色与版面。
- 最终对照：`outputs/新旧对照.png`（作者原图 / v1 复刻版 / B 版终稿）。

## 同方向整站扩展（2026-10-05）

- 用户接受沿用既有视觉，要求标普均线偏离单独成页，三个入口统一为三个按钮。
- 原话：「1、这个页面新增加一个入口，不要和美股信息日报与预警共用一个页面；2、基于第 1 点，你把这个页面的 3 个入口按照页面的视觉风格做成 3 个按钮；3、其他均接受」。
- 采用 B 的米白底、宋体标题、等宽数字和墨色分隔线；既定方向内迭代，不重新选择风格。
