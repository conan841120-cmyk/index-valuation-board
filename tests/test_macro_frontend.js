const assert=require('assert');
const M=require('../web/macro.js');
const rows=[{date:'2019-12',leading_indicator:0,hsi_close:25000},
  {date:'2020-01',leading_indicator:null,hsi_close:24000},
  {date:'2020-02',leading_indicator:null,hsi_close:23000},
  {date:'2020-03',leading_indicator:-1,hsi_close:22000},
  {date:'2020-04',leading_indicator:0.1,hsi_close:22500},
  {date:'2020-05',leading_indicator:null,hsi_close:null}];
const before=JSON.stringify(rows);
assert.deepStrictEqual(M.gaps(rows),[[{coord:['2019-12',0]},{coord:['2020-03',-1]}]]);
const option=M.mainOption(rows);
assert.strictEqual(option.series[0].connectNulls,false);
assert.strictEqual(option.series[0].data[1],null);
assert.strictEqual(option.series[0].markLine.data.length,1);
assert.strictEqual(option.series[0].markLine.lineStyle.type,'dashed');
assert.strictEqual(option.series[0].markLine.silent,true);
assert.strictEqual(M.select(rows,'ALL').length,6);
assert.strictEqual(M.select(rows,'3').length,3);
assert.strictEqual(M.gaps(M.select(rows,'4')).length,0);
assert(M.csv(rows).split('\n')[2].startsWith('2020-01,,24000,'));
assert.strictEqual(JSON.stringify(rows),before);
const roundSource={label:'PPI同比',current_round:{window_start:'2026-10-08',window_end:'2026-10-14',observation_period:'2026-09',status:'awaiting'},next_round:{window_start:'2026-11-08',window_end:'2026-11-14',observation_period:'2026-10'},backlog_rounds:[]};
assert(M.roundTable([roundSource]).includes('本轮尚未取得'));
assert(!M.roundTable([roundSource]).includes('已取得本轮数据'));
const delayed={...roundSource,current_round:{...roundSource.current_round,status:'acquired'},backlog_rounds:[{window_start:'2026-09-08',window_end:'2026-09-14',observation_period:'2026-08'}],last_probe_error:'HTTP 503 <test>'};
const statusHtml=M.roundTable([delayed]);
assert(statusHtml.includes('已取得本轮数据'));
assert(statusHtml.includes('旧轮次待补：2026-08（原区间 2026-09-08 至 2026-09-14）'));
assert(statusHtml.includes('HTTP 503 &lt;test&gt;'));
assert(statusHtml.includes('2026-11-08'));
console.log('宏观前端验证通过：空值、虚线、边界、范围筛选和CSV导出。');
