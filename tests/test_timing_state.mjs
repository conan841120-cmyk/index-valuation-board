import assert from 'node:assert/strict';
import {timingStatus} from '../web/sp500/timing-state.mjs';
const data={expected_date:'2026-11-13',calendar_until:'2027-12-01',due_at:'2026-11-14T07:00:00+08:00',sessions:[{date:'2026-11-12',close_at:'2026-11-12T21:00:00Z'},{date:'2026-11-13',close_at:'2026-11-13T21:00:00Z'}]};
const fresh={latest:{date:'2026-11-13',kind:'A',trend:true}},old={latest:{date:'2026-11-12',kind:'A'},successful_at:'old'};
assert.equal(timingStatus(data,fresh,Date.parse('2026-11-15T12:00:00Z')).current,true);
assert.equal(timingStatus(data,old,Date.parse('2026-11-13T22:00:00Z')).title,'等待更新／历史结果');
assert.equal(timingStatus(data,old,Date.parse('2026-11-14T01:00:00Z')).title,'历史结果');
assert.equal(timingStatus(data,{},Date.parse('2026-11-14T01:00:00Z')).title,'暂不可判定');
assert.equal(timingStatus(data,{...fresh,error:'failed'},Date.parse('2026-11-14T01:00:00Z')).current,false);
assert.equal(old.successful_at,'old');
console.log('timing-state: 6 assertions passed');

const {normalizeTimingSnapshot}=await import('../web/sp500/timing-state.mjs');
const validRow={eligible:true,date:'2026-11-13',close:100,ma200:98,prior_ma200:97,ma5:101,r5:-.04,volatility:.01,threshold:-.02,deviation:100/98-1,trend_change:98/97-1,multiple:4,kind:'A',trend:true,near:false,conflict:false,first_date:'2026-11-13',consecutive:1,start_known:true};
const valid={...data,schema_version:1,strategy:'strategy-v1.0',checked_at:'2026-11-14T00:00:00Z',indices:{sp500:{symbol:'SPX',latest:{...validRow},successful_at:'2026-11-14T00:00:00Z',error:null},ndx:{symbol:'NDX',latest:{...validRow},successful_at:'2026-11-14T00:00:00Z',error:null}}};
assert.equal(normalizeTimingSnapshot(valid).indices.ndx.latest.close,100);
for(const mutate of [x=>x.indices.ndx.latest.close='bad-price',x=>x.indices.ndx.symbol='SPX',x=>delete x.indices.ndx.latest.ma5,x=>x.indices.ndx.latest.close=Infinity,x=>x.indices.ndx.latest.close=null,x=>x.indices.ndx.latest.near='yes',x=>delete x.indices.ndx.successful_at]){
 const broken=structuredClone(valid);mutate(broken);const checked=normalizeTimingSnapshot(broken);
 assert.equal(checked.indices.ndx.latest,undefined);assert.ok(checked.indices.ndx.error.startsWith('数据无效'));
 assert.equal(timingStatus(checked,checked.indices.ndx).title,'暂不可判定');assert.equal(checked.indices.sp500.latest.close,100);
}
for(const mutate of [x=>x.schema_version=2,x=>x.strategy='wrong',x=>x.sessions={},x=>delete x.expected_date]){
 const broken=structuredClone(valid);mutate(broken);const checked=normalizeTimingSnapshot(broken);
 assert.equal(checked.indices.sp500.latest,undefined);assert.equal(checked.indices.ndx.latest,undefined);
}
console.log('Timing snapshot boundary: valid JSON wrong type/identity/missing/nonfinite fields isolated');

const {historyView}=await import('../web/sp500/timing-state.mjs');
const rounds={rows:[{...validRow,date:'2025-11-12',first_date:'2025-11-12',kind:'A',consecutive:1},{...validRow,date:'2025-11-13',first_date:'2025-11-12',kind:'B',consecutive:2},{...validRow,date:'2025-11-14',first_date:'2025-11-12',kind:'A',consecutive:3},{...validRow,date:'2026-11-13',first_date:null,kind:null,consecutive:0}]};
const preserved=JSON.stringify(rounds);
assert.equal(historyView(rounds,'all').markers.length,1);
assert.equal(historyView(rounds,'all','AB',true).markers.length,3);
const cropped=historyView(rounds,'1');
assert.equal(cropped.signals.length,2);assert.equal(cropped.markers[0].date,'2025-11-13');
assert.equal(cropped.markers[0].first_date,'2025-11-12');assert.equal(cropped.markers[0].consecutive,2);assert.equal(cropped.markers[0].continuation,true);
assert.equal(historyView(rounds,'all','B').markers[0].first_date,'2025-11-12');
assert.equal(historyView(rounds,'all','B').markers[0].roundId,historyView(rounds,'all','A').markers[0].roundId);
assert.equal(JSON.stringify(rounds),preserved);
const payload=structuredClone(valid);
payload.indices.ndx.history={schema_version:1,strategy:'strategy-v1.0',symbol:'NDX',source:'Unit fixture',source_sha256:'a'.repeat(64),generated_at:'2026-11-14T00:00:00Z',price_start:'2026-11-13',price_end:'2026-11-13',eligible_start:'2026-11-13',sessions:['2026-11-13'],rows:[{...validRow}]};
assert.equal(normalizeTimingSnapshot(payload).indices.ndx.history.rows.length,1);
for(const mutate of [x=>x.indices.ndx.history.rows[0].close='invalid',x=>x.indices.ndx.history.symbol='SPX',x=>x.indices.ndx.history.sessions.push('2026-11-14'),x=>x.indices.ndx.history.rows[0].consecutive=9]){
 const v=structuredClone(payload);mutate(v);const result=normalizeTimingSnapshot(v);
 assert.equal(result.indices.ndx.history,undefined);assert.ok(result.indices.ndx.history_error);
 assert.equal(result.indices.sp500.latest.close,100);assert.equal(result.indices.ndx.latest.close,100);
}
console.log('Historical view: first/all, A/B continuation, crop boundaries, immutable source and malformed-history isolation passed');
