export const STARTS=[1950,1970,2000,2010];
export const WINDOWS=[5,20,60];
export const LEVELS={60:[3,5,8,10,15],200:[5,10,15,20,25]};
export const ERA_COLORS=['#2e4a6b','#9a7736','#8a1f12','#5c6b45'];
export const pct=v=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'—';
export const signed=v=>Number.isFinite(v)?(v>=0?'+':'')+v.toFixed(2)+'%':'—';
export const num=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:2});
export const ci=r=>!r?.n?'无成熟样本':r.bootstrap_degenerate?'区间退化，勿解读':r.p_up_ci95.map(pct).join('–');
export const bin=r=>!r?'无对应区间':r.bin_low==null?'低于 '+r.bin_high+'%':r.bin_high==null?r.bin_low+'% 及以上':r.bin_low+'% ～ '+r.bin_high+'%';
export const inBin=(v,r)=>(r.bin_low==null||v>=r.bin_low)&&(r.bin_high==null||v<r.bin_high);
export const quantile=(a,p)=>{const i=(a.length-1)*p,l=Math.floor(i);return a[l]+(a[Math.ceil(i)]-a[l])*(i-l);};
export const rank=(a,v)=>100*upperBound(a,v)/a.length;
function upperBound(a,v){let lo=0,hi=a.length;while(lo<hi){const m=(lo+hi)>>1;if(a[m]<=v)lo=m+1;else hi=m;}return lo;}
export function summary(rows,ma){
 const values=rows.map(r=>r['bias'+ma]).sort((a,b)=>a-b),mean=values.reduce((a,b)=>a+b,0)/values.length;
 return {values,n:values.length,mean,median:quantile(values,.5),q5:quantile(values,.05),q95:quantile(values,.95),min:values[0],max:values.at(-1),sd:Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/values.length)};
}
export function rollingBand(rows){
 const sorted=[],queue=[];let first=0;
 return rows.map(r=>{const cutoff=new Date(r.date+'T00:00:00Z');cutoff.setUTCFullYear(cutoff.getUTCFullYear()-5);const start=cutoff.toISOString().slice(0,10);
  while(first<queue.length&&queue[first].date<start){const old=queue[first++];sorted.splice(upperBound(sorted,old.bias200)-1,1);}
  sorted.splice(upperBound(sorted,r.bias200),0,r.bias200);queue.push(r);
  return {...r,q5:sorted.length>=1000?quantile(sorted,.05):null,q95:sorted.length>=1000?quantile(sorted,.95):null};
 });
}
