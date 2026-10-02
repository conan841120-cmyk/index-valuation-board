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
console.log('宏观前端验证通过：空值、虚线、边界、范围筛选和CSV导出。');
