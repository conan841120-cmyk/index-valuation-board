import React, {useMemo, useRef, useLayoutEffect, useState} from 'react';

import {STARTS,ERA_COLORS,pct,signed,num,rank} from './model.mjs';
export * from './model.mjs';
export function Gauge({stats,value}){
 const pos=v=>Math.max(0,Math.min(100,100*(v-stats.min)/(stats.max-stats.min)));
 return <div className="sp-gauge" data-reviewed-rows><div className="sp-gauge-track" role="img" aria-label={'当前 '+signed(value)+'，第 '+rank(stats.values,value).toFixed(1)+' 百分位'}>
  {[stats.q5,stats.median,stats.q95].map((v,i)=><i key={i} style={{left:pos(v)+'%'}}/>)}<b style={{left:pos(value)+'%'}}/>
 </div><div className="sp-gauge-labels"><span>5% 分位<b>{signed(stats.q5)}</b></span><span>中位数<b>{signed(stats.median)}</b></span><span>95% 分位<b>{signed(stats.q95)}</b></span></div></div>;
}
const NO_MARKERS=[];
function sample(rows,fields,limit){
 if(rows.length<=limit)return rows;
 const selected=new Set([0,rows.length-1]),step=Math.ceil(rows.length/(limit/(fields.length*2)));
 for(let i=0;i<rows.length;i+=step){for(const f of fields){let lo=i,hi=i;for(let j=i;j<Math.min(i+step,rows.length);j++){if(rows[j][f]<rows[lo][f])lo=j;if(rows[j][f]>rows[hi][f])hi=j;}selected.add(lo);selected.add(hi);}}
 return [...selected].sort((a,b)=>a-b).map(i=>rows[i]);
}
function useWidth(){const ref=useRef(null),[width,setWidth]=useState(900);useLayoutEffect(()=>{const observer=new ResizeObserver(([entry])=>setWidth(Math.max(240,entry.contentRect.width)));observer.observe(ref.current);return ()=>observer.disconnect();},[]);return [ref,width];}
export function LinePlot({rows,fields,colors,labels,log=false,domain,band=false,zones=false,height=260,compact=false,current,ariaLabel,xField='date',fraction=false,verticalAt,highlight,price=false,markers=NO_MARKERS,selectedDate=null,onSelect,rowNote}){
 const [ref,width]=useWidth(),[hover,setHover]=useState(null),[keyboard,setKeyboard]=useState(0);
 const left=compact?48:64,right=18,top=18,bottom=height-32;
 const times=useMemo(()=>rows.map(r=>xField==='date'?Date.parse(r.date):r[xField]),[rows,xField]);
 const rowX=r=>xField==='date'?Date.parse(r.date):r[xField];
 const x=t=>left+(t-times[0])/(times.at(-1)-times[0]||1)*(width-left-right);
 const extent=useMemo(()=>{if(domain)return domain;const vals=rows.flatMap(r=>fields.map(f=>r[f])).filter(Number.isFinite);let lo=Math.min(...vals),hi=Math.max(...vals);if(log)return [lo*.9,hi*1.1];if(fraction)return [0,hi*1.12||1];const pad=(hi-lo)*.12||1;return [price?lo-pad:Math.min(0,lo-pad),hi+pad];},[rows,fields.join(','),domain,log,fraction,price]);
 const scale=v=>log?Math.log(v):v,y=v=>bottom-(scale(v)-scale(extent[0]))/(scale(extent[1])-scale(extent[0]))*(bottom-top);
 const plotted=useMemo(()=>{const sampled=sample(rows,[...fields,...(band?['q5','q95']:[])],compact?500:1800);if(!markers.length)return sampled;return [...new Map([...sampled,...markers].map(r=>[r.date,r])).values()].sort((a,b)=>a.date.localeCompare(b.date));},[rows,fields.join(','),band,compact,markers]);
 const path=f=>{let open=false;return plotted.map(r=>{if(!Number.isFinite(r[f])){open=false;return '';}const part=(open?'L':'M')+x(rowX(r)).toFixed(1)+','+y(r[f]).toFixed(1);open=true;return part;}).join('');};
 const active=hover??(selectedDate?rows.findIndex(r=>r.date===selectedDate):-1),row=active<0?null:rows[active],tickCount=compact?3:Math.max(3,Math.min(7,Math.floor(width/140))),ticks=Array.from({length:5},(_,i)=>log?Math.exp(scale(extent[0])+(scale(extent[1])-scale(extent[0]))*i/4):extent[0]+(extent[1]-extent[0])*i/4);
 const atPointer=e=>{const bounds=e.currentTarget.getBoundingClientRect(),t=times[0]+((e.clientX-bounds.left-left)/(width-left-right))*(times.at(-1)-times[0]);let lo=0,hi=times.length-1;while(lo<hi){const m=(lo+hi)>>1;if(times[m]<t)lo=m+1;else hi=m;}setHover(lo);setKeyboard(lo);};
 return <div className="sp-plot" ref={ref} data-reviewed-rows><svg width="100%" height={height} viewBox={'0 0 '+width+' '+height} role="img" aria-label={ariaLabel} data-fields={fields.join(',')} data-domain={extent.join(',')} tabIndex={0} onMouseMove={atPointer} onMouseLeave={()=>setHover(null)} onFocus={()=>setHover(keyboard)} onBlur={()=>setHover(null)} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,keyboard+(e.key==='ArrowLeft'?-1:1)));setKeyboard(next);setHover(next);}}}>
  {zones&&<><rect x={left} y={top} width={width-left-right} height={Math.max(0,y(15)-top)} className="sp-zone-top"/><rect x={left} y={y(-15)} width={width-left-right} height={Math.max(0,bottom-y(-15))} className="sp-zone-bottom"/></>}
  {ticks.map(v=><g key={v}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} className="sp-gridline"/><text x={left-8} y={y(v)+4} textAnchor="end">{log||price?num(Math.round(v)):fraction?pct(v):v.toFixed(0)+'%'}</text></g>)}
  {band&&['q5','q95'].map(f=><g key={f}><path d={path(f)} className="sp-percentile-line" data-indicator={f==='q5'?'5%分位':'95%分位'}><title>{f==='q5'?'5%分位':'95%分位'} · 最新 {signed(rows.at(-1)[f])}</title></path>{compact&&<text x={left+4} y={y(rows.at(-1)[f])-4}>{f==='q5'?'5%分位':'95%分位'} {signed(rows.at(-1)[f])}</text>}</g>)}
  {current!=null&&<><line x1={left} x2={width-right} y1={y(current)} y2={y(current)} className="sp-current-line"/><text x={width-right-2} y={y(current)-5} textAnchor="end" className="sp-current-text">当前 {signed(current)}</text></>}
  {highlight&&<path d={path(highlight)+'L'+x(times.at(-1))+','+bottom+'L'+x(times[0])+','+bottom+'Z'} fill={colors[highlight]} opacity={.12}/>}
  {fields.map(f=><path key={f} d={path(f)} fill="none" stroke={colors[f]} strokeWidth={f===highlight?2.5:compact?1.4:1.8}/>)}
  {verticalAt!=null&&<><line x1={x(verticalAt)} x2={x(verticalAt)} y1={top} y2={bottom} className="sp-current-line"/><text x={Math.min(width-right,Math.max(left,x(verticalAt)))} y={top+8} textAnchor="middle" className="sp-current-text">当前 {signed(verticalAt)}</text></>}
  {Array.from({length:tickCount},(_,i)=>{const t=times[0]+(times.at(-1)-times[0])*i/(tickCount-1);return <text key={i} x={x(t)} y={height-8} textAnchor={i===0?'start':i===tickCount-1?'end':'middle'}>{xField==='date'?new Date(t).toISOString().slice(0,7):t.toFixed(0)+'%'}</text>;})}
  {markers.map(r=><g key={r.date} className="timing-marker" role="button" tabIndex={0} aria-label={r.kind+'类信号 '+r.date+' 收盘 '+num(r.close)+(r.continuation?'（延续标记）':'')} aria-pressed={r.date===selectedDate} data-date={r.date} data-kind={r.kind} data-close={r.close} onMouseMove={e=>{e.stopPropagation();setHover(rows.findIndex(row=>row.date===r.date));}} onFocus={e=>{e.stopPropagation();setHover(rows.findIndex(row=>row.date===r.date));}} onClick={()=>onSelect?.(r.date)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();onSelect?.(r.date);}}}>
   <title>{r.date} · {r.kind}类 · 收盘{num(r.close)}{r.continuation?' · 本轮延续':''}</title><circle cx={x(rowX(r))} cy={y(r.close)} r="13" fill="transparent"/>
   {r.kind==='A'?<circle cx={x(rowX(r))} cy={y(r.close)} r={r.date===selectedDate?7:4.5} fill="#49764c" stroke={r.date===selectedDate?'#17140f':'#fff'} strokeWidth={r.date===selectedDate?2.5:1}/>:<path d={'M'+x(rowX(r))+','+(y(r.close)-7)+'l7,7l-7,7l-7,-7Z'} fill="#bf7734" stroke={r.date===selectedDate?'#17140f':'#fff'} strokeWidth={r.date===selectedDate?2.5:1}/>}
  </g>)}
  {selectedDate&&rows.some(r=>r.date===selectedDate)&&<text className="timing-selected-date" x={Math.max(left+40,Math.min(width-right-40,x(Date.parse(selectedDate))))} y={top+10} textAnchor="middle">{selectedDate}</text>}
  {row&&<line x1={x(times[active])} x2={x(times[active])} y1={top} y2={bottom} className="sp-hover-line"/>}
 </svg>{row&&<div className="sp-plot-tooltip" role="status" style={{left:Math.min(Math.max(0,x(times[active])-75),Math.max(0,width-210))}}><strong>{xField==='date'?row.date:Math.floor(row[xField])+'% ～ '+Math.ceil(row[xField])+'%'}</strong>{[...fields,...(band?['q5','q95']:[])].map(f=><span key={f}>{labels[f]??(f==='q5'?'5%分位':'95%分位')} <b style={{color:colors[f]}}>{log||price?num(row[f]):fraction?pct(row[f]):signed(row[f])}</b></span>)}{rowNote&&<span>{rowNote(row)}</span>}</div>}</div>;
}
export function ThresholdBars({rows,levels,metric,horizon}){
 const [ref,width]=useWidth(),height=330,left=48,right=12,top=32,bottom=284,group=(width-left-right)/levels.length,bw=Math.min(44,(group-16)/4);
 return <div ref={ref} className="sp-bars" data-reviewed-rows><div className="sp-legend">{STARTS.map((y,i)=><span key={y}><i style={{background:ERA_COLORS[i]}}/>{y}年以来</span>)}</div><svg width="100%" height={height} viewBox={'0 0 '+width+' '+height} role="img" aria-label={horizon+'交易日后'+(metric==='p_up'?'上涨':'下跌')+'概率，柱内标注事件数'}>
  {[0,.25,.5,.75,1].map(v=><g key={v}><line x1={left} x2={width-right} y1={bottom-v*(bottom-top)} y2={bottom-v*(bottom-top)} className="sp-gridline"/><text x={left-7} y={bottom-v*(bottom-top)+4} textAnchor="end">{Math.round(v*100)}%</text></g>)}
  {levels.map((q,j)=><g key={q}><text x={left+group*(j+.5)} y={height-14} textAnchor="middle">{signed(q)}</text>{STARTS.map((y,i)=>{const r=rows.find(r=>r.threshold_pct===q&&r.start_year===y),v=r?.[metric],x=left+group*(j+.5)+(i-2)*bw,h=Number.isFinite(v)?v*(bottom-top):0;return <g key={y} tabIndex={0} role="img" aria-label={y+'年以来，阈值'+q+'%，'+pct(v)+'，'+(r?.n??0)+'次事件'}><title>{y}年以来 · {signed(q)} · {pct(v)} · n={r?.n??0} · {r?.bootstrap_degenerate?'区间退化':r?.[metric+'_ci95']?.map(pct).join('–')}</title><rect x={x+1} y={bottom-h} width={bw-2} height={h} rx={3} fill={ERA_COLORS[i]} opacity={r&&(r.n<30||r.event_years<5)?.55:.88}/><text x={x+bw/2} y={bottom-h-7} textAnchor="middle" className="sp-bar-value">{Number.isFinite(v)?Math.round(v*100)+'%':'—'}</text><text x={x+bw/2} y={h>35?bottom-12:bottom-h-23} textAnchor="middle" className={h>35?'sp-bar-n':'sp-bar-value'}>{r?.n??0}</text></g>;})}</g>)}
 </svg></div>;
}
