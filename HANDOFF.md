# HANDOFF — 指数估值看板（index-valuation-board）

> 复制定位：本文件是**项目交接文档**，接手任何与本项目相关的任务前先读它。
> 2026-10-02用户选择修复预览版作为集成基线，并授权把恒生指数领先指标部署到原页面。独立集成目录保留最新云端估值输入；原版与修复预览目录继续保留。
> 云端仓库：`conan841120-cmyk/index-valuation-board`（公开）　本地：`~/Documents/DSH/index-valuation-board/`

## 1. 项目一句话

复刻「研究员雷牛牛」公众号日更估值图 / 理杏仁「历史PE/PB」页的**信息结构与统计口径**，
用**免费公开数据源**重建 5 个重点指数的估值看板（含可视页面、每日云端自动更新、作者口径变化监控）。

## 2. 背景与用户画像（必须遵守）

- 用户**不懂编程**：先解释清楚再动手，用中文，结论先给，不确定就直说不确定。
- **一次只做 1–2 个小功能**，每阶段停下来等验收，不要一口气铺开。
- **密钥红线**：绝不要求用户把 API key / token 贴进聊天；需要时让他自己放进 GitHub Secrets 或本机配置。
- **GitHub First**：写代码前先用 `gh search repos` 查有没有现成实现（本项目的复用情况见 §8）。
- 用户的 Mac 经常睡眠 → 需要定时跑的一律放云端（GitHub Actions）。本项目已上云。
- 用户会明确说"这里不用改"（如字体配色已验收定稿），**不要顺手优化**。

## 3. 环境与入口（接手后第一个检查清单）

| 项 | 值 |
| --- | --- |
| 本地项目路径 | `~/Documents/DSH/index-valuation-board/` |
| 云端看板 | https://conan841120-cmyk.github.io/index-valuation-board/ |
| 仓库 / 工作流 | `conan841120-cmyk/index-valuation-board` · `.github/workflows/daily.yml` |
| Python | 系统 `python3`（3.9.x）+ `requests / pandas / numpy / xlrd / openpyxl / Pillow`（见 `requirements.txt`） |
| OCR | `tesseract`（macOS `/opt/homebrew/bin/tesseract`，需 `chi_sim`；Actions 用 apt 安装） |
| 图表库 | `web/vendor/echarts.min.js`（已内置，页面离线可用） |
| 回归测试 | `python3 -m unittest discover -s tests -v`（以实际测试输出为准） |

## 4. 系统运行机制（现状）

```
fetch/   fetch_danjuan.py  → 蛋卷：PE/PB 长历史（周频，2016-09 起）+ 当前 PE/PB/股息率
         fetch_csindex.py  → 中证官方：日频点位（含每日 PE 字段）+ 官方估值文件（市盈率1/2、股息率1/2，仅近 20 交易日）
         fetch_tencent.py  → 腾讯行情：美股指数点位（usNDX / us.INX）
         derive_yield.py   → 股息率历史推导（全收益法 + PE 锚定法 + 近端衰减校准）
compute/ config.py         → 唯一需要人工维护的「业务规则」：指数表、口径、方向、阈值、时间窗口
         normalize.py      → 统一成周频（每周最后一个交易日）
         stats.py          → 12 项统计量（口径见 §8）+ 分位点/标准差视图序列
         build_dataset.py  → 装配 data/dashboard.json（含 rule_watch 口径核对结论）
         run_all.py        → 入口：抓取（失败自动沿用上次快照）→ 装配
         report.py         → outputs/口径与误差报告.md（与作者截图逐项对照）
web/     template.html + app.js + render.py → 打包成单文件 outputs/估值看板.html
tools/   watch_rule.py     → 口径变化监控（见 §4.2）
```

### 4.1 云端（原有单条 UTC 00:30 schedule，北京名义 08:30）

`daily.yml`：抓数据 → 重算 → 口径核对 → 生成报告 → 渲染 `docs/index.html` → 回归测试 → 回写快照 → 发布 Pages。
- 任一路数据源失败：有有效旧缓存时沿用并标出失败；无有效缓存时明确记录缺失，完整性检查决定是否中止。
- 回归测试不通过：**中止发布**，避免把错数据推上线。
- **发布闸门的构成**——结构/公式检查与有效的同期截图判定共同组成闸门：
  1. **结构/口径**：5 个指数齐、口径正确（含"红利低波=股息率"护栏）、方向、12 项统计量齐、A500 真实区间声明；
  2. **公式单元测试**（`tests/test_stats.py`）：固定输入 → 固定输出（分位取值/分位点/z/方向）；
  3. **自洽性检查**（`tests/test_replication.py::TestInternalConsistency`）：危险≥中位≥机会（反向对调）、分位点 0~100、
     z 合理、末点=数据日、各窗口点数单调、10Y≈500 点——公式或装配被改坏会立刻红，且永不因行情漂移误报；
  4. **同期截图比对**：仅当基准 `data_date` == 本期 `data_date` 时才判定；过期基准跳过（偏差写进报告）。
- 手动触发：`gh workflow run daily.yml`；查运行：`gh run list --limit 3`。
- 本副本保留原有一条 `30 0 * * *` cron。定时任务可能排队、延迟或未执行，不保证准点完成。
- 外部定时器仅为**未启用备选**（`tools/TRIGGER.md`）：需要单仓最小权限、短有效期 Token，且增加第三方存储风险。
  HTTP 204 只代表请求被接受，必须核对 Actions 构建、部署成功与页面日期；不保证到点必跑。

### 4.2 口径变化监控（tools/watch_rule.py）

作者会改口径（2026-09-23 红利低波用市净率LF，09-27 改成股息率），所以每天核对：
1. **发现文章**：公众号「合集」接口 `mp/appmsgalbum?action=getalbum&__biz=...&album_id=...` **免登录**返回最近文章；
   按标题正则 `【YYYY-MM-DD】…核心指数估值` 取最新一篇（`ALBUM` 常量在 `tools/watch_rule.py` 顶部）。
2. **取配图**：文章页里 `cdn_url/width/height` 列表，取宽度 >500 的内容图（正文是 JS 注入的，HTML 里没有正文文本）。
3. **识别指数**：对图顶部一行（y≈140~230）做 OCR（tesseract chi_sim+eng），优先按指数代码匹配。
4. **识别口径**：工具栏第一行被选中的指标按钮是**整块填蓝** `#4EABC4`，按蓝色色块中心 x 与标定表 `BUTTONS` 比对。
5. **比对**：与 `compute/config.py` 的 `metric` 比对；不一致 → 页面顶部红条 + 页脚 ❌ + 退出码 2（不阻塞发布）。
6. **页面取哪次结论**：渲染前会重读一次 `rule_check.json`（`web/render.py::with_fresh_rule_watch`），
   页面显示的永远是**最新**一次核对结论，与工作流步骤顺序无关（写进 `dashboard.json` 的只是装配那一刻的快照）。

## 5. 已完成（DONE）

- 统计公式由单元测试与自洽性检查核验；截图对齐只在存在同期同口径基准时判定，测试数以当前输出为准。
- 5 个指数：纳斯达克100（PE）· 标普500（PE）· 中证A500（PE）· 红利低波（**股息率，反向**）· 中证红利（股息率，反向）。
- 页面（视觉方向 B · 财经数据新闻版面，用户 2026-09-27 验收定稿）：指数切换、3Y/5Y/10Y/全部可用、
  指标切换（含并排真实 PE/PB 序列）、视图切换（指标/分位点/标准差）、读数表、明细数据、移动平均、
  CSV 导出、自定义分位阈值（⚙）、≈ 推导标注、调仓标志、小倍数并置、口径核对行。
- 云端每日自动更新 + Pages 发布 + 快照回写（首次运行实测：5 个指数全部数据源真抓成功，无风控）。
- 口径监控上线，2026-09-27 首次核对：命中 5 个指数，全部一致。
- 设计过程留档：`design/design-spec.md`、`design/direction-approved.md`、`design/design-demos/`（三方向初稿 + 截图）。

## 6. 已知问题与卡点

| # | 问题 | 影响 | 现状 |
| --- | --- | --- | --- |
| 1 | 主股息率历史是 current_anchor **事后估算** | 截图拟合容差不是历史/未来误差保证，不可作为当时可知的择时信号 | 当前主锚点仍为蛋卷第三方口径；官方 dy1 逐日累积成独立 alternate；dy2 保留在数据文件，不混入主历史；阴影按用户要求保留，命名为“阈值附近的观察缓冲区”，仅作人为设定的视觉提醒（美股2%、红利5%），不作误差或置信区间解释 |
| 2 | 中证A500 官方 PE 仅自 2024-09-03 起（指数 2024-09-23 发布，估值不回溯） | 只有 2 年真实区间，无法与作者 10 年分位点对齐 | 页面只展示真实区间并明示；不做推算 |
| 3 | 数据商口径差异（蛋卷 vs 中证官方 vs 理杏仁） | 不同定义不能互相冒充或拼接 | 来源、指标日期、价格日期和生成时间分开记录；本期截图核验状态由报告动态生成 |
| 4 | 免费版 GitHub Pages 只能用于公开仓库 | 仓库与数据公开；用户名含数字（用户已决定**不改名**） | 如需私有：迁 Cloudflare Pages + 仓库转私有（免费） |
| 5 | GitHub Actions schedule 的执行时间无准点保证 | 名义时间不等于执行/部署完成时间 | 保留原有单 cron；外部触发仅未启用备选（`tools/TRIGGER.md`），需检查实际运行结果 |
| 6 | 本机沙箱限制 | 写 `~/.dsh/skills`、`~/.codex/skills`、`~/.cache/gh` 被拒；Swift Vision OCR 不可用 | skill 装到工作区 `.dsh/skills/`；OCR 用 tesseract；`gh` 日志改用 API 取 |

## 7. 下一步计划（NEXT）

1. 手机竖屏排版（当前按 1440 桌面宽设计，手机上整体缩放偏小）。
2. 多指数同图对比（5 个指数分位点放一张图）。
3. 自定义时间区间（拖选起止日期，替代固定 3Y/5Y/10Y）。
4. 关键结论微信推送（可复用用户 us-trader-daily 的 PushPlus 通道；token 由用户自填 Secrets）。
5. 评估理杏仁等历史数据源，先核对定义与日期覆盖；付费本身不保证口径对齐。
6. **把「数值级」校验也长期自动化**：`tools/watch_rule.py` 每天已经拿到作者当天的图，可进一步 OCR 出图上的数字
   （当前值/分位点/危险值/中位数/机会值）做**同期**比对——这才是唯一严谨的比对方式（见 §8 坑 19）。
   过渡办法：把作者新图的数值录入 `data/reference/screenshots.json` 并写上 `data_date`，同期校验即自动恢复。

## 8. 踩坑记录（坑 → 解法 → 防复发）

**口径类**

1. 作者 2026-09-23 给"红利低波"用了**市净率LF**，09-27 改成**股息率**（用户指出 PB 对红利指数不合理）。
   → 解法：以 09-27 为准；`tests/test_replication.py` 加回归护栏（断言 `dividend_low_vol.metric == "dy"`）；
   再加 `tools/watch_rule.py` 每天自动核对作者口径。
2. 统计口径必须按"分位取整"理解，否则差很多：升序序列第 `⌊p·n⌋` 项（自 0 起），**不是线性插值**；
   分位点 = `count(x < 当前值)/n`；z 分数 = `(当前值−平均)/样本标准差(ddof=1)`；反向指标（股息率/风险溢价）危险值取 20 分位、机会值取 80 分位。
3. 作者图的"起始日期"要分清：中证A500 的官方估值字段首日是 **2024-09-03**，而周频首点是 **2024-09-06**
   （2024-09-03~09-06 同属一周，取该周最后一个交易日）→ 页脚分别标注，不要混为一谈。

**图表类**

4. 调仓标志（散点）曾挂在**左轴（估值轴）**上，把左轴量程从"股息率 2.65~7.65"拉成"0~8000"，
   表现为"左侧纵轴看不到 / 估值面积消失"。→ 解法：散点改挂**右轴（点位轴）**，y 取点位轴最小值，`symbolOffset:[0,-5]` 贴底。
5. 散点的 x 必须落在**真实存在的周频点**上（否则被静默丢弃，表现为"有的指数一个三角都没有"）
   → 解法：把调仓日吸附到 `dates[k] >= d` 的第一个周频点。
6. 点位轴量程由 ECharts 自己取整，各指数不同 → 三角被垫到不同高度。→ 解法：用自写 `niceStep/levelAxis` 显式钉住右轴 min/max/interval。
7. x 轴只显示两位年份数字（`17 18 19`）既不像日期又稀疏；且一个月有 4~5 个周频点会被重复标注
   → 解法：`YY-MM` 格式；>4 年按半年、短窗口按季度；同月只取第一个周点。
8. `web/render.py` 的 `slim()` 会丢掉未显式保留的顶层字段（曾导致 `rule_watch` 不显示）→ 新增字段要同步 `slim()`。

**数据源类**

9. 微信公众号正文是 JS 注入的，HTML 里没有正文文本 → 取图要从 `cdn_url` + `width/height` 列表解析（宽度 >500 的是内容图）。
10. 公众号历史消息接口（`profile_ext`）无 cookie 返回"验证"页；搜狗微信账号搜索无结果
    → 改用**合集接口** `appmsgalbum`（免登录，返回最近文章标题/链接/时间）。
11. 东方财富接口高频请求后会 `Empty reply from server`（限流）→ 加退避；美股点位主用腾讯、东财作备选。
12. 中证官方估值文件只有最近约 20 个交易日 → 每次运行落盘累积（`data/official_snapshots/*.csv`），装配读取累计文件；dy1 是独立 alternate，dy2 保存在数据文件，两者均不能与蛋卷主股息率混合。
13. 中证 `perf` 接口的 `peg` 字段**就是市盈率（TTM 口径）**：沪深300 与雪球 PE 完全吻合、中证红利差 1%（别被字段名误导）。

**工具类**

14. macOS 无头 Chrome 截图必须给 `--user-data-dir`（否则报 "Failed to create headless user data directory"），
    且必须 `kill -9`（否则进程不退出，会把命令拖到超时）→ 见 `web/screenshot.sh`。
15. 沙箱里 Swift Vision OCR 报 unknownError → 用 `tesseract --psm 7 -l chi_sim+eng` 识别图顶部一行足够准。
16. 长串命令（抓取+OCR+渲染+测试）会超时 → **分步执行**；抓取用 `nohup ... &` + 轮询日志。
17. 指令链里 `git pull --rebase` 在存在未提交改动时失败 → 先提交/暂存再 rebase。
18. 页面上的「口径核对」行曾**永远落后一次运行**（2026-09-28 修复）：工作流里「口径变化监控」跑在
    「抓取 + 重算」之后，而装配（`build_dataset.py`）在那一刻就把结论写进了 `dashboard.json`；渲染只读
    `dashboard.json` → 作者当天改口径，页面红条要晚一天才出现。
    → 解法：渲染时用 `rule_watch_payload()` 重读 `data/watch/rule_check.json` 覆盖旧副本
    （`web/render.py::with_fresh_rule_watch`），与步骤顺序解耦；`tests/test_rule_watch.py` 加回归护栏。
19. 发布闸门曾**拿过期快照判数字**（2026-09-28 修复）：作者的数字每天也在重算，而 `data/reference/screenshots.json`
    里的基准是**冻结**的 → 行情一动（中证A500 五天差 4.43%）或当前值一漂移（股息率差 `0.030000000000000025 > 0.03`）
    就把 CI 判红，而 `daily.yml` 是「测试不过就不发布」→ **看板停止更新**（它拦住的不是错误，只是时间差）。
    → 解法：闸门只保留与时间无关的判定（结构/口径、`test_stats` 公式单元测试、`TestInternalConsistency` 自洽性）；
    截图数值比对仅在「基准 `data_date` == 本期 `data_date`」时判定，过期基准只写进 `outputs/口径与误差报告.md`；
    浮点边界一律加 `EPS=1e-9`。想让「同期校验」重新生效：录入作者新图数值时带上 `data_date`（该图对应的数据日）。

## 9. 运维速查

```bash
cd '/Users/sherlock/Documents/DSH修复预览/index-valuation-board'

# 本地修复预览（不抓取、不部署）
python3 tools/verify_local.py              # 重建 → 报告 → 渲染 → 测试

# 原项目数据 + 页面
python3 compute/run_all.py                 # 抓取 + 重算（单源失败自动沿用上次快照）
python3 compute/run_all.py --rebuild       # 跳过抓取，用现有 raw_inputs.json 重算
python3 compute/report.py                  # → outputs/口径与误差报告.md
python3 web/render.py                      # → outputs/估值看板.html（双击可看）
python3 -m unittest discover -s tests -v    # 以实际测试输出为准

# 口径监控
python3 tools/watch_rule.py                # 自动找最新日更文章并核对口径
python3 tools/watch_rule.py --images-dir <目录>   # 离线核对已有图片

# 截图 / 对比图
./web/screenshot.sh "$PWD/outputs/估值看板.html?index=sp500" /tmp/x.png 1440 1000
python3 web/compare.py                     # v1 复刻版 vs 作者原图（数据核对图）

# 云端
gh workflow run daily.yml                  # 立刻跑一次
gh run list --limit 3                      # 看最近运行
gh api repos/conan841120-cmyk/index-valuation-board/actions/runs/<id>/jobs   # 看每一步结论
curl -sI https://conan841120-cmyk.github.io/index-valuation-board/ | head -1 # 看站点是否在线

# 改口径（唯一需要人工维护的业务规则）
vim compute/config.py     # 指数表：metric（pe/pb/dy/rp）、direction、sources、rebalance
```

## 10. 交接清单（本文件被读取后的动作）

1. 跑 `python3 tools/verify_local.py`：先离线重建 → 报告 → 渲染 → 测试，校验当前输入/代码指纹；不要先测试旧 dashboard。
2. 本修复副本只打开 `outputs/估值看板.html` 验收；本地通过不代表已部署。
3. 想看"数据可信度"，读 `outputs/口径与误差报告.md`：同期核验字段与失败数动态统计，无同期基准即本期未验证。
4. 想改口径/换指数：**只改 `compute/config.py`**，然后 `run_all.py → report.py → render.py → 测试`。
5. 口径监控若报不一致：先看页面顶部红条列出的差异，再决定改 `config.py`（以作者当天口径为准）还是保持本项目口径。
6. 任何"顺手优化"前先问用户——视觉（B 方向）已验收定稿，字体/配色/版面不要改。
