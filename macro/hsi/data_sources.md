# 数据来源清单

下表的起止是**非空数据**范围；观察期和发布日期另存为列。详细每个对象的 URL、状态码、SHA256 和下载时间见 `output/diagnostics/raw_manifest.json`。

| dataset | institution | official_name | URL | frequency | unit | start_date / latest | observation_date_rule | release_date_available | download_method | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Retail YoY | 国家统计局 NBS | 社会消费品零售总额同比增长 (%) | [国家数据](https://data.stats.gov.cn/dg/website/index.html)；[流式接口](https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData) | 月 | % | 2000-01 / 2026-08 | code YYYYMM；当月同比 | 部分，约2021-10起，46个非空值有日期 | 指标目录 GET，数据 POST JSON | 字段ID aaac57d54d2e465d91bc9f3ea1a8618e；累计同比排除；1—2月官方空白不补 |
| PPI YoY | NBS | 工业生产者出厂价格指数，上年同月=100 | 同上 | 月 | 同比指数减100→% | 1993-01 / 2026-08 | YYYYMM；上年同月比较 | 部分，59个月 | 同上 | ID 150633e52b9a470a9a9fd1b296dd6c5b；不是环比或购进价格 |
| Nominal GDP | NBS | 国内生产总值当季值 (亿元)，现价 | 同上 | 季 | CNY_100million | 1992Q1 / 2026Q2 | YYYYQQSS→quarter；单季金额 | 2021Q3起20季，初步核算表公告日 | 同上 | ID d22612f09aeb4241bc557ef0ac61b3ba；排除实际增速/累计金额 |
| Social financing flow | 中国人民银行 PBOC | 社会融资规模增量统计表 AFRE(flow) | [年度数据目录](https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html)；[早期历史PDF](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2863557/2021122418533735135.pdf) | 月 | CNY_100million | 2002-01 / 2026-08 | YYYY.MM；当月增量 | 2011-06起173个月；有缺口已标记 | 2012以后年度HTML；2002—2011 PDF | 年度重叠优先较新官方文件；剔除百分比附录；非存量、非累计；统计范围有扩展 |
| HK M2 total YoY | 香港金融管理局 HKMA | Table 1A Money Supply / M2 / Total / % change over earlier same month | [官方新闻档案](https://www.hkma.gov.hk/eng/news-and-media/press-releases/)；逐月 release/annex_url 在 hk_m2.csv | 月 | % | 2011-08 / 2026-08 | Monetary Statistics for [month year] | 完整181月，实际 publish_date | 官方新闻档案API，逐月PDF/XLS/XLSX附件 | 全货币Total官方同比，显示1位小数；不是HK$组件、季调、环比、M1或M3 |
| HSI early monthly close | 香港交易所 HKEX | Hang Seng Index, daily closing | [2012年鉴](https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Reports/HKEX-Fact-Book/HKEx-Fact-Book-2012/fb_2012.pdf)、[2013年鉴](https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Reports/HKEX-Fact-Book/HKEx-Fact-Book-2013/fb_2013.pdf) | 日→月 | index_points | 使用2012-07 / 2013-12 | 每月最后有报价的交易日 | 年鉴发布日未核验；仅用于比较 | PDF第24页日收盘表 | 非宏观输入；不得把年鉴发布时间当当时收盘可得日期 |
| HSI recent official close | HKEX | Monthly Market Highlights / Hang Seng Index | [月报](https://www.hkex.com.hk/Market-Data/Statistics/Consolidated-Reports/HKEX-Monthly-Market-Highlights?sc_lang=en) | 月 | index_points | 当前选择器2025-08 / 2026-08 | 官方月末收盘 | 不作为宏观门控输入；最后交易日独立取日线 | HTML；select=公开GUID | 与新浪交叉核验后优先官方报价 |
| HSI middle / latest close | 新浪财经 | HSI 日K线 close | [日线原件](https://finance.sina.com.cn/stock/hkstock/HSI/klc_kl.js) | 日→月 | index_points | 原件2013-08 / 2026-09 | 完整月最后交易日；当前未结束月份排除 | 最后交易日，非供应商发布批次日期 | 压缩JS缓存；纯数学解码 | 唯一主要第三方数值源；只比较。重叠官方月末价格误差≤0.001点 |
| NBS release dates | NBS | 最新发布 / 初步核算结果及月度公报 | [发布索引](https://www.stats.gov.cn/sj/zxfb/) | 按公告 | date | 当前可访问索引约2021-10 / 2026-09 | 从标题确定对应月份/季度 | 实际列表日期 | 67个公开索引页 HTML | 不从迁移URL目录推断发布日期；历史日历含计划而非实际日期，未用 |
| PBOC release dates | PBOC | 社融增量/金融统计数据报告 | [统计发布目录](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html)；[2025-01原公告补充](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554594361/index.html) | 按公告 | date | 2011-06 / 2026-09 | 标题观察月份；季度累计报告对应季末月 | 实际列表/正文日期 | 38个公开索引页 HTML；核验合并报告正文 | 2025-01补充实际2025-02-14；不是URL迁移日2025-09-22 |

## 官方调查中排除的对象

- NBS 旧 easyquery 接口 HTTP 403；新版首页短历史不足；某些旧/非流式接口返回错误。改用同一机构的新版公开流式接口成功，未用第三方替换宏观数据。
- HKMA `supply-components-all` 官方 API 请求超时；官方 `MSB/T020202.xls` 是余额，不符合直接同比优先；政府统计处表 340-45011 的 M2 YoY CSV 实际是季度，不能充当月度；C01 是 HK$ M3，也排除。最后找到官方每月新闻附件的 M2 Total 直接同比，全历史已获取，**没有余额同比替代**。
- 社零 1—2 月没有独立当月同比；未把累计字段或合并公报值擅自替代。PPI 直接指数减100只是单位表达，不是由原始金额计算同比。
- Yahoo/Stooq 请求超时或不可访问，腾讯端点失败。恒指随后采用新浪及 HKEX 核验；宏观输入未切换。失败下载不计为成功。
- PBOC 旧数字ID的2025-01公告路径HTTP404；通过官方新闻列表找到迁移后的实际公告，实际日期以正文为准。

## 版本与单位

NBS=latest-vintage revised history；PBOC=revised annual mixed vintages；HKMA=逐月发布附件。当前四项不是完整历史 as-released-vintage 集合。金额先换算为亿元后相除。同比原始值统一以百分数输入，信用脉冲以比例输入，分别标准化后各自量纲消除。

## 2026-10-01 AnySearch 调查的备用源（未用于主指标）

| dataset | institution | official_name / provider field | URL | frequency | unit | start_date | observation_date_rule | release_date_available | download_method | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Retail YoY backup | 东方财富 Choice | RETAIL_TOTAL_SAME；社会消费品零售总额当月同比 | [页面](https://data.eastmoney.com/cjsj/xfp.html)；https://datacenter-web.eastmoney.com/api/data/v1/get | 月 | % | 2008-01 | REPORT_DATE取年月；非下载月 | API无逐条实际发布日期 | reportName=RPT_ECONOMY_TOTAL_RETAIL，pageSize=1000，209行/1页完整JSON | 194有效同比；与NBS重叠194/194一致；2013起JanFeb不能补；latest available history，非vintage档案 |
| Retail YoY recent cross-check | 同花顺金融研究中心 | 同比；当月值列后第1个同比列 | [页面](https://data.10jqka.com.cn/macro/xfp/) | 月 | % | 本次有效值2024-03 | YYYY-MM；与累计同比分开 | 未提供逐条实际发布日期 | HTML近期30行表；26有效同比 | 26/26一致；未获得全历史导出；不充当完整月度来源 |
| Retail YoY rejected backup | 新浪财经 | 社会消费品零售总额同比增长；源键名与金额口径相反，已单独核验 | [页面](https://finance.sina.com.cn/mac/)；https://quotes.sina.cn/mac/api/jsonp_v3.php | 月 | % | 本次有效值2001-02 | 年.月转换年月；从公开配置确认nation/event13 | 未提供逐条实际发布日期 | MacPage_Service.get_pagedata，完整请求+尾部重叠请求 | 267有效同比，38差异；count552 vs534唯一返回月份未对账，不声称全历史已完整下载 |
| Retail current-period levels, excluded | ChinaData | Total Retail Sales of Consumer Goods (current period) | [API](https://chinadata.live/api/v2/data/china-retail-sales) | 月 | 亿元 | 2007-01 | API date YYYY-MM | 未核验实际发布日期 | 206行完整响应JSON | 非直接同比，JanFeb仍缺，不自行计算同比替代 |

搜索由 AnySearch 服务完成，返回原始结果及请求ID缓存于 `data/raw/anysearch_*`。第三方数据仅用于本次对照，未改变首选官方源；完整状态、失败下载、置信边界见 `output/RETAIL_ALTERNATIVE_SOURCE_REPORT.md`。
