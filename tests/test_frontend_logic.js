/* Offline regression checks for display semantics. No APIs or browser packages. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const points = Array.from({length:10},(_,i)=>({date:`2026-09-${String(i+1).padStart(2,'0')}`,value:i,level:null,kind:'derived',source:'danjuan',value_date:'2026-09-09',level_date:null}));
const stats={current:9,percentile:90,danger:2,median:5,opportunity:8,zone:'低估',level:null,n:10,start:'2026-09-01',end:'2026-09-10'};
const main={key:'x',name:'测试',code:'X',metric:'dy',metric_label:'股息率',flag:'derived',source:'danjuan',data_date:'2026-09-10',digits:2,direction:'inverse',stats:{'3Y':stats},views:{'3Y':{start:0,pct:points.map((_,i)=>i*10),z:[]}},series:points,value_meta:{calibration:{applied:false}},sources:{danjuan:true},source_status:{danjuan:{ok:false,at:'2026-09-30',last_success_at:'2026-09-10',last_data_date:'2026-09-10'}},alternates:{}};
main.alternates.official_dy={metric:'dy',metric_label:'中证官方股息率1',flag:'real',source:'csindex',data_date:'2026-09-02',digits:2,direction:'inverse',stats:{ALL:{...stats,n:2}},views:{ALL:{start:0,pct:[0,50],z:[-1,1]}},series:points.slice(0,2).map(p=>({...p,source:'csindex',kind:'real'}))};
const nodes={};
function node(){return {innerHTML:'',textContent:'',style:{},children:[],appendChild(v){this.children.push(v);},setAttribute(){},querySelectorAll(){return [];},querySelector(){return node();},click(){}};}
let csvBlob;
const dashboard={indices:[main],windows:['3Y','ALL'],default_window:'3Y',generated_at:'2026-09-30T10:00:00+08:00'};
const sandbox={window:{DASHBOARD:dashboard},document:{readyState:'loading',addEventListener(){},getElementById(id){return nodes[id]||(nodes[id]=node());},createElement:node},echarts:{init(){return {setOption(){},resize(){},dispose(){}};}},Blob:class {constructor(parts){csvBlob=parts.join('');}},URL:{createObjectURL(){return 'blob:test';},revokeObjectURL(){}}};
let code=fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8');
code=code.replace("  if(document.readyState==='loading')", "  window.test={state,grp,metricData,thresholds,thresholdPcts,validPcts,zoneFor,baseOption,renderLead,renderReadout,renderColophon,renderAll,exportCsv,watchStatus};\n  if(document.readyState==='loading')");
vm.runInNewContext(code,sandbox);
const t=sandbox.window.test;t.state.key='x';t.state.metricKey='dy';t.state.win='3Y';
assert.equal(t.grp(null),'—');
assert.equal(t.thresholdPcts(main).danger,20);
let thresholds=t.thresholds(main,stats,'3Y');
let p={i:main,data:main,s:stats,t:thresholds,view:'percentile',pts:points,main:[],label:'分位点'};
let option=t.baseOption(p,false);assert.equal(option.series[0].markLine.data[0].yAxis,20);assert.equal(option.series[0].markLine.data[2].yAxis,80);
t.state.thr['x:dy']={danger:0,median:30,opportunity:95};thresholds=t.thresholds(main,stats,'3Y');
assert.equal(thresholds.danger,0);assert.equal(thresholds.opportunity,9);assert.equal(t.zoneFor(main,stats,thresholds),'合理偏低');
assert.equal(t.validPcts({danger:80,median:50,opportunity:20},true),false);
assert.equal(t.validPcts({danger:0,median:50,opportunity:100},true),true);
main.source_status.official={ok:false,at:'2026-09-30'};
main.source_status.csindex_perf={ok:false,at:'2026-09-30',last_data_date:'2026-09-11'};
main.level_date='2026-09-29';main.change_date='2026-09-30';
main.alternates.official_dy.series[1].level_date='2026-09-02';
let ctx=t.renderLead();assert.match(nodes.stance.innerHTML,/3Y分位点/);assert.doesNotMatch(nodes.stance.innerHTML,/十年/);t.renderReadout(ctx);assert.match(nodes.notes.innerHTML,/推导估算/);assert.match(nodes.notes.innerHTML,/不能直接用于回测/);assert.doesNotMatch(nodes.notes.innerHTML,/官方真实值|±6pp|偏差 ≤5%/);
t.renderColophon(ctx);assert.match(nodes.colophonLeft.innerHTML,/抓取失败，沿用旧数据/);
assert.match(nodes.colophonLeft.innerHTML,/中证官方估值：抓取失败/);
assert.match(nodes.colophonLeft.innerHTML,/中证指数行情：抓取失败/);
assert.match(nodes.colophonLeft.innerHTML,/数据日期 未记录/);
assert.match(nodes.colophonLeft.innerHTML,/蛋卷（雪球系）/);assert.match(nodes.colophonLeft.innerHTML,/上次成功 2026-09-10/);
t.exportCsv();assert.match(csvBlob,/window,ranks_basis,kind,series_kind,source,value_date,level_date/);assert.match(csvBlob,/"derived","derived","danjuan"/);
let asked, alertCount=0;
const gear={getAttribute(){return 'danger';}};
nodes.readTable.querySelectorAll=()=>[gear];
sandbox.window.prompt=(message,current)=>{asked=current;return null;};
sandbox.window.alert=()=>{alertCount++;};
t.renderReadout(ctx);gear.onclick();assert.equal(asked,0);
sandbox.window.prompt=()=> '60';gear.onclick();assert.equal(alertCount,1);assert.equal(t.state.thr['x:dy'].danger,0);
sandbox.window.prompt=()=> '';gear.onclick();assert.equal(t.state.thr['x:dy'],undefined);
nodes.readTable.querySelectorAll=()=>[];
t.state.metricKey='official_dy';let alt=t.metricData();assert.equal(alt.metric_key,'official_dy');assert.equal(alt.source,'csindex');assert.equal(alt.flag,'real');assert.equal(alt.data_date,'2026-09-02');assert.equal(main.metric_key,undefined);
t.renderAll();assert.equal(t.state.win,'ALL');
assert.match(nodes.leadPrice.textContent,/该序列点位日期 2026-09-02/);
assert.match(nodes.colophonRight.innerHTML,/该序列点位日期 2026-09-02/);
assert.match(nodes.colophonRight.innerHTML,/最新涨跌日期 2026-09-30/);
assert.match(nodes.colophonLeft.innerHTML,/估值来源：中证指数官方/);
assert.match(nodes.multiples.children.at(-1).innerHTML,/默认阈值/);assert.match(nodes.notes.innerHTML,/独立真实对照/);assert.match(nodes.notes.innerHTML,/不与主股息率的推导历史拼接/);assert.doesNotMatch(nodes.readTable.innerHTML,/推导估算/);
const good={state:'consistent',checked_at:'2026-09-30 09:00:00',article_date:'2026-09-30',matched:5,missing:[]};dashboard.rule_watch=good;assert.equal(t.watchStatus().ok,true);
main.code='SPX.GI';t.renderAll();assert.match(nodes.alert.innerHTML,/估值与最新行情日期不同/);
main.latest_level=7801.77;main.latest_level_date='2026-10-07';
main.source_status.danjuan={ok:true,at:'2026-10-08',last_data_date:'2026-09-10',freshness:'lagging',reference_date:'2026-10-07'};
t.renderAll();assert.match(nodes.leadPrice.textContent,/最新行情点位 7,801.77（2026-10-07）/);
assert.match(nodes.leadPrice.textContent,/估值图对应点位/);
assert.match(nodes.leadPrice.textContent,/该序列点位日期 2026-09-02/);
assert.match(nodes.colophonLeft.innerHTML,/抓取成功，估值数据滞后/);
main.source_status.danjuan.ok=false;t.renderAll();
assert.match(nodes.colophonLeft.innerHTML,/抓取失败，沿用旧数据，估值数据滞后/);
main.source_status.danjuan.freshness='aligned';t.renderAll();
assert.match(nodes.colophonLeft.innerHTML,/估值与已取得行情日期一致/);
assert.doesNotMatch(nodes.colophonLeft.innerHTML,/估值数据滞后/);
main.source_status.danjuan.freshness='unknown';t.renderAll();
assert.match(nodes.colophonLeft.innerHTML,/估值新鲜度无法核验/);
main.code='X';
for(const patch of [{matched:4},{missing:['x']},{state:'incomplete'},{state:'failed'},{checked_at:'2026-09-28T10:00:00+08:00'},{checked_at:null}]){dashboard.rule_watch={...good,...patch};assert.equal(t.watchStatus().ok,false);}
const priceIndex={...main,level_series:[{date:'2026-09-30',value:100},{date:'2026-10-01',value:101},
  {date:'2026-10-02',value:102},{date:'2026-10-05',value:105},{date:'2026-10-06',value:106},{date:'2026-10-07',value:107}]};
const valuationPoints=[{date:'2026-09-28',value:25,level:98},{date:'2026-09-30',value:26,level:100}];
const pricePayload={i:priceIndex,data:{...main,data_date:'2026-09-30',series:valuationPoints,views:{'3Y':{pct:[40,50]}}},
  s:stats,t:thresholds,view:'metric',pts:valuationPoints,main:[25,26],label:'市盈率TTM'};
for(const view of ['metric','percentile','std']){
 const plot=t.baseOption({...pricePayload,view},false);
 assert.equal(plot.xAxis.type,'time');assert.equal(plot.useUTC,true);
 assert.deepEqual(Array.from(plot.series[0].data,x=>new Date(x[0]).toISOString().slice(0,10)),
   ['2026-09-28','2026-09-30','2026-10-01','2026-10-02','2026-10-05','2026-10-06','2026-10-07']);
 assert.deepEqual(Array.from(plot.series[0].data,x=>x[1]),[25,26,null,null,null,null,null]);
 assert.deepEqual(Array.from(plot.series[1].data,x=>x[1]),[98,100,101,102,105,106,107]);
 assert.equal(plot.series[0].connectNulls,false);
 const tip=plot.tooltip.formatter([{dataIndex:6}]);
 assert.match(tip,/2026-10-07/);assert.match(tip,/暂无估值数据（估值截止 2026-09-30）/);
 assert.match(tip,/点位 107.00/);assert.doesNotMatch(tip,/分位点/);
 assert.equal(plot.yAxis[1].max>=107,true);
}
assert.equal(valuationPoints.length,2);assert.deepEqual(pricePayload.main,[25,26]);
assert.equal(t.baseOption(pricePayload,true).xAxis.max,Date.parse('2026-10-07T00:00:00Z'));
const echarts=require('../web/vendor/echarts.min.js');
const weeklyPoints=[{date:'2026-09-21',value:24,level:97},...valuationPoints];
const weeklyPayload={...pricePayload,pts:weeklyPoints,main:[24,25,26],
  i:{...priceIndex,rebalance_dates:['2026-09-29']}};
for(const small of [false,true]){
 const plot=t.baseOption(weeklyPayload,small);
 const chart=echarts.init(null,null,{renderer:'svg',ssr:true,width:1000,height:300});
 chart.setOption(plot);
 const pixel=date=>chart.convertToPixel({xAxisIndex:0},Date.parse(date+'T00:00:00Z'));
 const day=pixel('2026-10-02')-pixel('2026-10-01');
 assert.ok(Math.abs((pixel('2026-09-28')-pixel('2026-09-21'))/day-7)<1e-8);
 assert.ok(Math.abs((pixel('2026-10-05')-pixel('2026-10-02'))/day-3)<1e-8);
 assert.equal(plot.xAxis.axisLabel.formatter(Date.parse('2026-10-01T00:00:00Z')),'26-10');
 assert.equal(plot.series[2].data[0][0],Date.parse('2026-09-30T00:00:00Z'));
 assert.equal(plot.series[2].data[0][1],plot.yAxis[1].min);
 const tip=small?'':plot.tooltip.formatter([{dataIndex:1,seriesIndex:1}]);
 if(!small){assert.match(tip,/2026-09-28/);assert.match(tip,/点位 98.00/);}
 chart.dispose();
}
priceIndex.level_series=[{date:'2026-09-30',value:100}];
assert.equal(t.baseOption(pricePayload,false).xAxis.max,Date.parse('2026-09-30T00:00:00Z'));
console.log('Frontend regression checks passed: threshold direction, custom zones, dates, alternate selection, CSV and watch state.');
