'use strict';
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {createHash} = require('node:crypto');
(async()=>{
 const SP=await import('../web/sp500/model.mjs');
 const rows=JSON.parse(readFileSync(require.resolve('../data/sp500/bootstrap.json'))).queries.daily.rows;
 assert.equal(SP.inBin(-10,{bin_low:-10,bin_high:-5}),true);
 assert.equal(SP.inBin(-5,{bin_low:-10,bin_high:-5}),false);
 assert.equal(SP.pct(null),'—');assert.equal(SP.pct(0),'0.0%');
 const bands=SP.rollingBand(rows);
 assert.equal(bands[998].q5,null);
 for(const i of [1300,5000,rows.length-1]){
  const cutoff=new Date(rows[i].date+'T00:00:00Z');cutoff.setUTCFullYear(cutoff.getUTCFullYear()-5);
  const observed=rows.slice(0,i+1).filter(r=>r.date>=cutoff.toISOString().slice(0,10)).map(r=>r.bias200).sort((a,b)=>a-b);
  assert.equal(bands[i].q5,SP.quantile(observed,.05));assert.equal(bands[i].q95,SP.quantile(observed,.95));
 }
 // Future closes must never change a previously plotted rolling percentile.
 assert.deepEqual(SP.rollingBand(rows.slice(0,5001)).at(-1),bands[5000]);
 for(const ma of [60,200]){
  const stats=SP.summary(rows,ma),last=rows.at(-1)['bias'+ma];
  assert.equal(stats.n,19310);
  assert.equal(SP.rank(stats.values,last),100*rows.filter(r=>r['bias'+ma]<=last).length/rows.length);
 }
 const hash=createHash('sha256');
 ['DashboardContent.jsx','visuals.jsx','model.mjs','ui.jsx','main.jsx'].forEach(file=>hash.update(readFileSync(require.resolve('../web/sp500/'+file))));
 assert.ok(readFileSync(require.resolve('../web/sp500.js'),'utf8').startsWith('// Source SHA-256: '+hash.digest('hex')+'\n'),'Bundled dashboard must match reviewed sources');
 console.log('S&P original dashboard, rolling percentile and asset checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
