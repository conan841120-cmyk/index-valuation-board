'use strict';
// Percent bias is expressed in percentage points; returns and probabilities are fractions.
const SP = {
  starts: [1950, 1970, 2000, 2010], horizons: [5, 20, 60],
  levels: {200: [5, 10, 15, 20, 25], 60: [3, 5, 8, 10, 15]},
  colors: ['#2e4a6b', '#8a1f12', '#5c6b45', '#9a7736'], charts: new Map(),
  pct(value, digits = 1) { return value == null ? '数据不足' : (value * 100).toFixed(digits) + '%'; },
  signed(value, digits = 1) { return value == null ? '—' : (value > 0 ? '+' : '') + value.toFixed(digits) + '%'; },
  pp(value) { return value == null || !Number.isFinite(value) ? '数据不足' : (value > 0 ? '+' : '') + (value * 100).toFixed(1) + ' 个百分点'; },
  point(value) { return value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}); },
  bin(row) {
    return row.bin_low == null ? '< ' + row.bin_high + '%' : row.bin_high == null ? '≥ ' + row.bin_low + '%' : '[' + row.bin_low + '%, ' + row.bin_high + '%)';
  },
  contains(row, bias) { return (row.bin_low == null || bias >= row.bin_low) && (row.bin_high == null || bias < row.bin_high); },
  quantile(sorted, q) { const i = (sorted.length - 1) * q; return sorted[Math.floor(i)] + (sorted[Math.ceil(i)] - sorted[Math.floor(i)]) * (i % 1); },
  ci(row, metric) {
    if (!row || !row.n) return '数据不足';
    const value = row[metric + (row.bootstrap_degenerate ? '_wilson_ci95' : '_ci95')];
    return value ? value.map(x => this.pct(x)).join('–') + (row.bootstrap_degenerate ? '（Wilson）' : '') : '—';
  },
  flag(row) { return !row.n ? '无样本' : [row.small_sample ? '小样本' : '', row.event_years < 5 ? '事件年份少' : '', row.bootstrap_degenerate ? '全胜／全败区间退化' : ''].filter(Boolean).join(' · '); },
  state(ma, bias, horizon = this.horizon) { return this.states.find(r => r.start_year === this.start && r.ma === ma && r.horizon === horizon && this.contains(r, bias)); },
  table(headers, rows) { return '<table><thead><tr>' + headers.map(h => '<th>' + h + '</th>').join('') + '</tr></thead><tbody>' + rows.join('') + '</tbody></table>'; },
  card(title, value, text) { return '<article class="summary"><div class="meta">' + title + '</div><div class="value">' + value + '</div><div class="meta">' + text + '</div></article>'; },
  chart(id, option) {
    let chart = this.charts.get(id);
    if (!chart) { chart = echarts.init(document.getElementById(id)); this.charts.set(id, chart); }
    chart.setOption({backgroundColor: 'transparent', color: this.colors, textStyle: {fontFamily: 'PingFang SC, sans-serif'}, ...option}, true);
  },
  axis() { return {axisLine: {lineStyle: {color: '#ded6c8'}}, axisLabel: {color: '#6a6156', fontSize: 12}, splitLine: {lineStyle: {color: '#e8e1d5'}}}; },
  current() {
    const latest = this.latest, bias = latest['bias' + this.ma], row = this.state(this.ma, bias);
    const baseline = this.baselines.find(r => r.start_year === this.start && r.horizon === this.horizon);
    const series = this.daily.filter(r => r.date >= this.start + '-01-01').map(r => r['bias' + this.ma]);
    const rank = series.filter(v => v <= bias).length / series.length;
    document.getElementById('setting').textContent = this.start + ' 年以来 · ' + this.ma + ' 日均线 · 未来 ' + this.horizon + ' 日';
    document.getElementById('current').innerHTML = this.card('当前偏离的历史位置', this.pct(rank), '百分位 · ' + this.signed(bias) + ' · 区间 ' + this.bin(row)) +
      this.card('相同区间期末上涨概率', this.pct(row.p_up), row.n + ' 个成熟交易日 / ' + row.event_years + ' 年 · 95%区间 ' + this.ci(row, 'p_up')) +
      this.card('与无条件样本相比', this.pp(row.p_up - baseline.p_up), '无条件上涨 ' + this.pct(baseline.p_up) + ' · 区间平均收益 ' + this.pct(row.mean_return));
  },
  history() {
    const start = document.getElementById('history-start').value;
    const recent = (Number(this.latest.date.slice(0, 4)) - 5) + this.latest.date.slice(4);
    const rows = this.daily.filter(r => r.date >= (start === 'recent' ? recent : start + '-01-01'));
    const dates = rows.map(r => r.date);
    const line = (key, name, axis, color) => ({name, type: 'line', xAxisIndex: axis, yAxisIndex: axis, data: rows.map(r => r[key]), showSymbol: false, sampling: 'lttb', lineStyle: {width: axis ? 1.3 : 1.5}, itemStyle: {color}});
    this.chart('history', {legend: {top: 0, textStyle: {fontSize: 12}}, tooltip: {trigger: 'axis', valueFormatter: v => v == null ? '—' : Number(v).toFixed(2)},
      grid: [{left: 60, right: 22, top: 50, height: '43%'}, {left: 60, right: 22, top: '62%', bottom: 42}],
      xAxis: [0, 1].map(i => ({...this.axis(), type: 'category', gridIndex: i, data: dates, axisLabel: {...this.axis().axisLabel, formatter: v => v.slice(0, 7), hideOverlap: true}})),
      yAxis: [{...this.axis(), type: 'log', name: '指数（对数）'}, {...this.axis(), gridIndex: 1, name: '偏离 %'}],
      dataZoom: [{type: 'inside', xAxisIndex: [0, 1]}],
      series: [line('close', '标普收盘', 0, '#14100c'), line('sma60', '60 日均线', 0, '#8a1f12'), line('sma200', '200 日均线', 0, '#2e4a6b'), line('bias60', '60 日偏离', 1, '#8a1f12'), {...line('bias200', '200 日偏离', 1, '#2e4a6b'), markLine: {silent: true, symbol: 'none', label: {show: false}, lineStyle: {color: '#6a6156', width: 1}, data: [{yAxis: 0}]}}]});
  },
  eras() {
    document.getElementById('eras').innerHTML = this.starts.map(year => '<article class="era"><h3>' + year + ' 年以来</h3><div class="meta" id="era-meta-' + year + '"></div><div class="chart" id="era-' + year + '" role="img" aria-label="' + year + '年以来偏离度"></div></article>').join('');
    // Dispose charts whose DOM nodes have just been replaced.
    for (const year of this.starts) { const old = this.charts.get('era-' + year); if (old) {old.dispose(); this.charts.delete('era-' + year);} }
    const full = this.daily.map(r => r['bias' + this.ma]), low = Math.floor(Math.min(...full) / 10) * 10, high = Math.ceil(Math.max(...full) / 10) * 10;
    const stats = [], distributions = [];
    const bins = Array.from({length: high - low + 1}, (_, i) => low + i);
    this.starts.forEach((year, i) => {
      const rows = this.daily.filter(r => r.date >= year + '-01-01'), values = rows.map(r => r['bias' + this.ma]), sorted = [...values].sort((a, b) => a - b);
      const mean = values.reduce((s, x) => s + x, 0) / values.length, sd = Math.sqrt(values.reduce((s, x) => s + (x - mean) ** 2, 0) / values.length);
      const rank = values.filter(v => v <= this.latest['bias' + this.ma]).length / values.length;
      document.getElementById('era-meta-' + year).textContent = rows.length.toLocaleString() + ' 日 · 5–95%分位 ' + this.signed(this.quantile(sorted, .05)) + ' 至 ' + this.signed(this.quantile(sorted, .95)) + ' · 当前第 ' + this.pct(rank) + ' 百分位';
      this.chart('era-' + year, {grid: {left: 42, right: 15, top: 18, bottom: 28}, tooltip: {trigger: 'axis', valueFormatter: v => Number(v).toFixed(2) + '%'},
        xAxis: {...this.axis(), type: 'category', data: rows.map(r => r.date), axisLabel: {...this.axis().axisLabel, formatter: v => v.slice(0, 4)}}, yAxis: {...this.axis(), min: low, max: high},
        series: [{name: this.ma + '日偏离', type: 'line', data: values, showSymbol: false, sampling: 'lttb', lineStyle: {width: 1.1}, itemStyle: {color: this.colors[i]}, markLine: {silent: true, symbol: 'none', label: {show: false}, lineStyle: {width: 1, color: '#6a6156'}, data: [{yAxis: 0}, {yAxis: this.latest['bias' + this.ma]}]}}]});
      stats.push('<tr><td>' + year + ' 以来</td>' + [mean, this.quantile(sorted, .5), sd, sorted[0], sorted[sorted.length - 1]].map(v => '<td class="num">' + this.signed(v) + '</td>').join('') + '<td class="num">' + this.pct(rank) + '</td></tr>');
      const counts = new Map(); values.forEach(v => counts.set(Math.floor(v), (counts.get(Math.floor(v)) || 0) + 1));
      distributions.push({name: year + ' 以来', type: 'line', showSymbol: false, data: bins.map(b => (counts.get(b) || 0) / values.length * 100), lineStyle: {width: 2}});
    });
    document.getElementById('distribution-stats').innerHTML = this.table(['时期', '平均偏离', '中位偏离', '标准差', '最低', '最高', '当前百分位'], stats);
    this.chart('distribution', {legend: {top: 0}, grid: {left: 52, right: 20, top: 42, bottom: 38}, tooltip: {trigger: 'axis', valueFormatter: v => Number(v).toFixed(2) + '%'},
      xAxis: {...this.axis(), type: 'category', data: bins, name: '偏离 %'}, yAxis: {...this.axis(), name: '交易日 %'}, series: distributions});
  },
  thresholds(side) {
    const metric = side === 'bottom' ? 'p_up' : 'p_down', sign = side === 'bottom' ? -1 : 1;
    const levels = this.levels[this.ma];
    this.chart(side + '-chart', {legend: {top: 0, textStyle: {fontSize: 12}}, tooltip: {trigger: 'axis', formatter: entries => entries.map(e => {const r = this.eventStats.find(r => r.start_year === this.starts[e.seriesIndex] && r.ma === this.ma && r.horizon === this.horizon && r.side === side && r.threshold_pct === sign * levels[e.dataIndex]); return e.marker + e.seriesName + '：' + this.pct(r[metric]) + ' / n=' + r.n + ' / ' + r.event_years + '年';}).join('<br>')},
      grid: {left: 48, right: 20, top: 45, bottom: 34}, xAxis: {...this.axis(), type: 'category', data: levels.map(n => (sign < 0 ? '低于 ' : '高于 ') + n + '%')},
      yAxis: {...this.axis(), min: 0, max: 100, axisLabel: {...this.axis().axisLabel, formatter: '{value}%'}},
      series: this.starts.map((year, i) => ({name: year + ' 以来', type: 'bar', barMaxWidth: 30, data: levels.map(n => {const r = this.eventStats.find(r => r.start_year === year && r.ma === this.ma && r.horizon === this.horizon && r.side === side && r.threshold_pct === sign * n); return {value: r.n ? r[metric] * 100 : null, itemStyle: {color: this.colors[i], opacity: r.n < 30 || r.event_years < 5 ? .4 : 1}};})}))});
  },
  scenario(point) {
    this.scenarioPoint = point;
    const b200 = Math.round(100 * (point / this.latest.sma200 - 1) * 1e10) / 1e10, b60 = Math.round(100 * (point / this.latest.sma60 - 1) * 1e10) / 1e10;
    document.getElementById('point').value = point; document.getElementById('b200').value = b200; document.getElementById('b60').value = b60;
    document.getElementById('point-output').textContent = this.point(point) + '（较当前 ' + this.signed(100 * (point / this.latest.close - 1)) + '）';
    document.getElementById('b200-output').textContent = this.signed(b200); document.getElementById('b60-output').textContent = this.signed(b60);
    const cards = [200, 60].map(ma => {
      const bias = Math.round((ma === 200 ? b200 : b60) * 1e10) / 1e10, row = this.state(ma, bias);
      return this.card(ma + ' 日偏离 ' + this.signed(bias) + ' · 区间 ' + this.bin(row), this.pct(row.p_up), '期末上涨 · n=' + row.n + ' / ' + row.event_years + '年 · 95%区间 ' + this.ci(row, 'p_up'));
    });
    const row = this.state(this.ma, this.ma === 200 ? b200 : b60);
    cards.push(this.card('期间曾跌 5% 的概率', this.pct(row.p_touch_down5), this.ma + ' 日区间 · 平均期末收益 ' + this.pct(row.mean_return) + ' · ' + (this.flag(row) || '仍需结合样本相关性判断')));
    document.getElementById('scenario').innerHTML = cards.join('');
  },
  heatmap() {
    const rows = this.states.filter(r => r.start_year === this.start && r.ma === this.ma && r.horizon === 5);
    document.getElementById('heatmap').innerHTML = this.table(['偏离区间', '5 个交易日', '20 个交易日', '60 个交易日'], rows.map(bin => '<tr' + (this.contains(bin, this.latest['bias' + this.ma]) ? ' class="row-current"' : '') + '><td class="num">' + this.bin(bin) + '</td>' + this.horizons.map(h => {
      const r = this.states.find(r => r.start_year === this.start && r.ma === this.ma && r.horizon === h && r.bin_low === bin.bin_low && r.bin_high === bin.bin_high);
      const color = !r.n ? 'transparent' : r.p_up >= .5 ? 'rgba(92,107,69,' + (.05 + (r.p_up - .5) * .5) + ')' : 'rgba(138,31,18,' + (.05 + (.5 - r.p_up) * .5) + ')';
      return '<td class="heatcell" style="background:' + color + '"><strong>' + this.pct(r.p_up) + '</strong><span>均值 ' + this.pct(r.mean_return) + ' · n=' + r.n + '</span><span>' + (this.flag(r) || r.event_years + ' 个年份') + '</span></td>';
    }).join('') + '</tr>'));
  },
  evidence() {
    const base = this.baselines.filter(r => r.start_year === this.start);
    document.getElementById('baseline').textContent = this.start + ' 年以来无条件基准：' + base.map(r => r.horizon + ' 日上涨 ' + this.pct(r.p_up) + ' / 下跌 ' + this.pct(r.p_down) + '（n=' + r.n + '）').join('；');
    const rows = this.eventStats.filter(r => r.start_year === this.start && r.ma === this.ma).sort((a, b) => a.threshold_pct - b.threshold_pct || a.horizon - b.horizon);
    document.getElementById('events-table').innerHTML = this.table(['穿越阈值', '未来交易日', '事件 / 年份', '上涨 / 95%区间', '下跌 / 95%区间', '平均 / 中位收益', '曾涨 / 跌 5%', '中位最大回撤', '相对基准上涨提升区间', '提示'], rows.map(r => '<tr><td class="num">' + this.signed(r.threshold_pct, 0) + '</td><td class="num">' + r.horizon + '</td><td class="num">' + r.n + ' / ' + r.event_years + '</td><td class="num">' + this.pct(r.p_up) + '<br><span class="meta">' + this.ci(r, 'p_up') + '</span></td><td class="num">' + this.pct(r.p_down) + '<br><span class="meta">' + this.ci(r, 'p_down') + '</span></td><td class="num">' + this.pct(r.mean_return) + ' / ' + this.pct(r.median_return) + '</td><td class="num">' + this.pct(r.p_touch_up5) + ' / ' + this.pct(r.p_touch_down5) + '</td><td class="num">' + this.pct(r.median_max_drawdown) + '</td><td class="num">' + (r.p_up_uplift_ci95 && !r.bootstrap_degenerate ? r.p_up_uplift_ci95.map(v => this.signed(v * 100)).join(' 至 ') + '点' : '数据不足') + '</td><td class="flag">' + this.flag(r) + '</td></tr>'));
    const events = this.events.filter(r => r.ma === this.ma && r.signal_date >= this.start + '-01-01').sort((a, b) => b.signal_date.localeCompare(a.signal_date) || a.threshold_pct - b.threshold_pct).slice(0, 20);
    document.getElementById('event-history').innerHTML = this.table(['信号日期', '穿越阈值', '参考日 / 收盘', '5 日收益', '20 日收益', '60 日收益'], events.map(r => '<tr><td class="num">' + r.signal_date + '</td><td class="num">' + this.signed(r.threshold_pct, 0) + '</td><td class="num">' + r.reference_date + ' / ' + this.point(r.reference_close) + '</td>' + this.horizons.map(h => '<td class="num">' + this.pct(r['return_' + h]) + '</td>').join('') + '</tr>'));
  },
  render() {
    this.start = Number(document.getElementById('start').value); this.ma = Number(document.getElementById('ma').value); this.horizon = Number(document.getElementById('horizon').value);
    this.current(); this.eras(); this.thresholds('bottom'); this.thresholds('top'); this.scenario(this.scenarioPoint); this.heatmap(); this.evidence();
  },
  async init() {
    const response = await fetch('snapshot.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error('snapshot unavailable');
    const data = await response.json();
    if (data.schema_version !== 1 || data.symbol !== '^GSPC') throw new Error('snapshot schema');
    for (const [target, source] of Object.entries({daily: 'daily', eventStats: 'event_stats', states: 'state_stats', baselines: 'baselines', events: 'events'})) this[target] = data.queries[source].rows;
    this.latest = this.daily[this.daily.length - 1]; this.scenarioPoint = this.latest.close;
    const status = document.getElementById('status'), state = data.refresh.state;
    const checked = new Date(data.refresh.checked_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'});
    status.textContent = '收盘截至 ' + data.research.data_end + ' · ' + (state === 'ok' ? '刷新成功' : state === 'failed' ? '刷新失败，保留上一版数据' : '已载入校验底稿，等待首次云端刷新') + ' · 最近检查 ' + checked + '（北京时间） · 每日 07:00';
    if (state === 'failed') status.classList.add('positive');
    document.getElementById('readings').innerHTML = [
      ['标普 500 收盘', this.point(this.latest.close), this.latest.date + ' · 价格指数'],
      ['与 200 日均线的距离', this.signed(this.latest.bias200), '均线 ' + this.point(this.latest.sma200)],
      ['与 60 日均线的距离', this.signed(this.latest.bias60), '均线 ' + this.point(this.latest.sma60)],
      ['最后成熟信号日', data.research.last_eligible_signal, '下一日参考价 + 完整 60 日窗口']
    ].map(([label, value, text]) => '<div class="reading"><div class="meta">' + label + '</div><div class="value">' + value + '</div><div class="meta">' + text + '</div></div>').join('');
    document.getElementById('provenance').textContent = '底稿校验 SHA-256：' + data.research.source_sha256;
    const point = document.getElementById('point'); point.min = Math.min(this.latest.sma60, this.latest.sma200) * .6; point.max = Math.max(this.latest.sma60, this.latest.sma200) * 1.4;
    point.addEventListener('input', e => this.scenario(Number(e.target.value)));
    [60, 200].forEach(ma => document.getElementById('b' + ma).addEventListener('input', e => this.scenario(this.latest['sma' + ma] * (1 + Number(e.target.value) / 100))));
    const quick = document.getElementById('quick');
    [-5, -10, -15, -25, 15].forEach(value => {const button = document.createElement('button'); button.textContent = '200 日偏离 ' + this.signed(value, 0); button.addEventListener('click', () => this.scenario(this.latest.sma200 * (1 + value / 100))); quick.append(button);});
    const reset = document.createElement('button'); reset.textContent = '回到当前'; reset.addEventListener('click', () => this.scenario(this.latest.close)); quick.append(reset);
    ['start', 'ma', 'horizon'].forEach(id => document.getElementById(id).addEventListener('change', () => this.render()));
    document.getElementById('history-start').addEventListener('change', () => this.history());
    window.addEventListener('resize', () => this.charts.forEach(chart => chart.resize()));
    this.render(); this.history();
  }
};
if (typeof module !== 'undefined') module.exports = SP;
if (typeof window !== 'undefined') SP.init().catch(() => {document.getElementById('status').textContent = '数据读取失败。请刷新页面；仍失败时暂不使用页面概率。';});
