// Standalone equivalents for the original dashboard's data and control components.
import React, {createContext, useContext, useMemo, useState} from 'react';
const DataContext=createContext(null);
export function DataProvider({snapshot,children}){
 const value=useMemo(()=>({snapshot,reviewedRows:id=>snapshot.queries[id].rows}),[snapshot]);
 return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}
export const useDataApp=()=>useContext(DataContext);
export function SegmentedControl({value,options,onChange,ariaLabel}){
 return <div className="data-segmented-control" role="group" aria-label={ariaLabel}>{options.map(o=><button type="button" key={o.value} aria-pressed={value===o.value} onClick={()=>onChange(o.value)}>{o.label}</button>)}</div>;
}
export function Switch({label,checked,onChange}){
 return <button type="button" className="data-switch" role="switch" aria-label={label} aria-checked={checked} onClick={()=>onChange(!checked)}>{label}<span aria-hidden="true"/></button>;
}
export function Slider({label,min,max,step,value,onChange,formatValue=String}){
 return <label className="data-slider">{label}<output>{formatValue(value)}</output><input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={e=>onChange(Number(e.target.value))}/></label>;
}
export function Dropdown({label,value,choices,formatChoice=String,onChange}){
 return <label className="data-dropdown">{label}<select aria-label={label} value={value} onChange={e=>onChange(e.target.value)}>{choices.map(v=><option key={v} value={v}>{formatChoice(v)}</option>)}</select></label>;
}
export const SortableRegion=({children,className,id})=><div id={id} className={className}>{children}</div>;
export const SortableItem=({children})=><div>{children}</div>;
function download(rows,title){
 const keys=[...new Set(rows.flatMap(Object.keys))],escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 const csv='\uFEFF'+[keys.map(escape).join(','),...rows.map(r=>keys.map(k=>escape(r[k])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=title+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function DataComponent({id,title,showHeading=true,className='',headerControls,displayRows=[],children}){
 const [showRows,setShowRows]=useState(false);
 return <section id={id} className={'dashboard-component '+className} aria-label={title}>
  <header className="component-header">{showHeading&&<h2 className="component-title">{title}</h2>}{headerControls&&<div className="component-header-controls">{headerControls}</div>}
   <details className="component-actions"><summary aria-label={title+' actions'}>···</summary><div><button onClick={()=>download(displayRows,title)}>下载数据 CSV</button><button onClick={()=>setShowRows(!showRows)}>查看数据</button></div></details>
  </header>{children}{showRows&&<div className="sp-details"><DataTable rows={displayRows} caption={title+' 数据'}/></div>}
 </section>;
}
export function DataTable({rows,columns=[],searchable=true,caption='数据',rowKey,pageSize=8}){
 const [search,setSearch]=useState(''),[order,setOrder]=useState({field:null,descending:false}),[page,setPage]=useState(0);
 const definitions=columns.length?columns:[...new Set(rows.flatMap(Object.keys))].map(field=>({field,label:field}));
 const visible=rows.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(search.toLowerCase()))).sort((a,b)=>{
  if(!order.field)return 0;const av=a[order.field],bv=b[order.field];
  const cmp=av==null?(bv==null?0:1):bv==null?-1:typeof av==='number'&&typeof bv==='number'?av-bv:String(av).localeCompare(String(bv));return order.descending?-cmp:cmp;
 });
 const pages=Math.max(1,Math.ceil(visible.length/pageSize)),current=Math.min(page,pages-1);
 return <>{searchable&&<input className="table-search" aria-label="Search data" placeholder="Search data" value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}}/>}
  <div className="table-wrap" role="region" aria-label={caption+' table'} tabIndex={0}><table className="table"><caption className="visually-hidden">{caption}</caption><thead><tr>{definitions.map(c=><th key={c.field} aria-sort={order.field===c.field?(order.descending?'descending':'ascending'):'none'}><button onClick={()=>setOrder({field:c.field,descending:order.field===c.field&&!order.descending})}>{c.label}{order.field===c.field?(order.descending?' ↓':' ↑'):''}</button></th>)}</tr></thead><tbody>{visible.slice(current*pageSize,(current+1)*pageSize).map((r,i)=><tr key={rowKey?r[rowKey]:i}>{definitions.map(c=><td key={c.field}>{c.renderCell?c.renderCell(r[c.field],r):r[c.field]==null?'—':String(r[c.field])}</td>)}</tr>)}</tbody></table></div>
  {(searchable||pages>1)&&<div className="table-pagination"><span>{visible.length?`${current*pageSize+1}–${Math.min((current+1)*pageSize,visible.length)} of ${visible.length} results`:'No results'}</span>{pages>1&&<div><span>Page {current+1} of {pages}</span><button aria-label="Previous page" disabled={!current} onClick={()=>setPage(current-1)}>‹</button><button aria-label="Next page" disabled={current+1>=pages} onClick={()=>setPage(current+1)}>›</button></div>}</div>}
 </>;
}
