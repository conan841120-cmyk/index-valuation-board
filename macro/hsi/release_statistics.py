"""Reproducible statistics of verified announcement dates, including Jan--Feb retail."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).parent
BOARD = ROOT.parents[1]


def build():
    policy = json.loads((ROOT / 'release_policy.json').read_text())
    nbs = pd.read_csv(ROOT / 'data/processed/nbs_release_dates.csv')
    sf = pd.read_csv(ROOT / 'data/processed/pboc_release_dates.csv').assign(dataset='social_financing')
    m2 = pd.read_csv(ROOT / 'data/processed/hk_m2.csv').rename(columns={'source_url': 'release_source_url'}).assign(dataset='hk_m2')
    columns = ['dataset', 'observation_period', 'release_date', 'release_source_url']
    records = pd.concat([nbs[columns], sf[columns], m2[columns]], ignore_index=True)
    records['published'] = pd.to_datetime(records.release_date, errors='coerce')
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    records = records[records.published.notna() & (records.published.dt.date <= today)]
    records = records.sort_values('published').drop_duplicates(['dataset', 'observation_period'])
    records['day'] = records.published.dt.day
    records['days_before_month_end'] = records.published.dt.days_in_month - records.day
    records['combined_retail_period'] = (records.dataset == 'retail') & records.observation_period.str.endswith('-02')
    output = BOARD / 'data/release_calendar'
    output.mkdir(parents=True, exist_ok=True)
    records.drop(columns='published').to_csv(output / 'verified_release_dates.csv', index=False)
    summaries = []
    for name, rule in policy['sources'].items():
        d = records[records.dataset == name]
        window = d.day.between(rule['start_day'], rule['end_day'])
        summaries.append({'dataset': name, 'label': rule['label'], 'n': len(d),
            'first_release': d.release_date.min(), 'last_release': d.release_date.max(),
            'median_day': float(d.day.median()), 'earliest_day': int(d.day.min()), 'latest_day': int(d.day.max()),
            'window': f"{rule['start_day']}—{rule['end_day']}日" if name != 'hk_m2' else '26日至月底',
            'window_coverage_pct': round(float(window.mean() * 100), 2),
            'outside_window_n': int((~window).sum())})
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / 'release_date_summary.csv', index=False)
    records.groupby(['dataset', 'day']).size().rename('count').reset_index().to_csv(output / 'release_day_counts.csv', index=False)
    lines = ['# 宏观指标实际公布日期统计与监测窗口', '', f'统计截至：{today}。仅使用官方实际公告日期，不用URL迁移日、计划日或下载日代替。', '',
        '信用脉冲没有独立的官方发布日期；监测社融增量和名义GDP两个输入。M2日期来自所用官方逐月新闻附件；统计局和社融日期来自官方发布列表。样本覆盖不等于完整历史，早期缺失日期不参与分母。', '',
        '|指标／输入|样本数|实际日期范围|中位日|监测窗口|历史覆盖率|窗口外样本数|', '|---|---:|---|---:|---|---:|---:|']
    for r in summaries:
        lines.append(f"|{r['label']}|{r['n']}|{r['first_release']}—{r['last_release']}|{r['median_day']:g}|{r['window']}|{r['window_coverage_pct']:.2f}%|{r['outside_window_n']}|")
    lines += ['', '## 样本的主要特征', '',
        '- 社零包含1—2月合并公告，但不把合并值填入两个独立月度值。2月没有独立1月数据发布轮次；3月核验1—2月合并公告。',
        '- PPI仍有独立月度发布轮次，不能套用社零的春节规则。',
        '- 香港M2全部样本在26日至月底；固定日历窗口不依赖工作日猜测。',
        '- GDP仅在1、4、7、10月监测；这里统计的是本项目使用的当季金额初步核算表公告日。',
        '- 社零和GDP的2022年第三季度相关公告延至2022-10-24。窗口外样本说明监测必须继续追踪，而非到窗口结束就停止。', '',
        '## 自动监测规则', '',
        '1. 各来源在其窗口内每天北京时间18:30轻量检查；窗口外且该轮已取得时，不访问该来源。估值日报独立每天08:30更新。',
        '2. 某轮窗口结束仍未取得对应观察期数据，则持续每天检查，直至取得。后面月份已有数据不能掩盖前面缺口。',
        '3. 进入该来源下一轮窗口仍缺上一轮数据，则网页持续显示报警；新报警让GitHub任务失败并留下说明。通知邮件是否送达取决于用户已有GitHub通知设置，不另建通知账户。',
        '4. 取得上一轮数据后报警自动解除。社零合并公告已确认但缺独立月度同比是正常的口径空值，不能当成异常。',
        '5. 轻量检查不扫描全历史：统计局查询近期月份/季度，人民银行核对当前年度最新附表，金管局查看相关月份发布目录。公告或数值变化才更新来源并重算。',
        '6. 同一URL下静默改写的历史数据不保证全部被轻量检查捕获；可以手动强制刷新。窗口规则固定在release_policy.json，不根据恒指表现调整。',
        '7. 两条云端流程共用发布锁，并在开始运行时检出最新main，避免覆盖另一部分的新快照。', '',
        '## 官方证据入口', '',
        '- 国家统计局：https://www.stats.gov.cn/sj/zxfb/',
        '- 人民银行：https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html',
        '- 香港金管局：https://www.hkma.gov.hk/eng/news-and-media/press-releases/',
        '- 每个样本的原公告链接见 data/release_calendar/verified_release_dates.csv。重跑：python macro/hsi/release_statistics.py。']
    (BOARD / 'RELEASE_CALENDAR_REPORT.md').write_text('\n'.join(lines) + '\n')
    return summary


if __name__ == '__main__':
    print(build().to_string(index=False))
