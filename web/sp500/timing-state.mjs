// Owns validation of untrusted timing.json. Rendering and status code consume only this shape.
export function normalizeTimingSnapshot(value){
 const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
 const date=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
 const instant=x=>typeof x==='string'&&/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(x)&&Number.isFinite(Date.parse(x));
 const unavailable=error=>({indices:{sp500:{error},ndx:{error}},error});
 if(!object(value))return unavailable('择时快照格式无效');
 if(typeof value.error==='string')return unavailable(value.error);
 if(value.schema_version!==1||value.strategy!=='strategy-v1.0')return unavailable('择时快照版本不支持');
 if(!object(value.indices)||!date(value.expected_date)||!date(value.calendar_until)||!instant(value.due_at)||!instant(value.checked_at)||!Array.isArray(value.sessions)||!value.sessions.length)
  return unavailable('择时快照缺少有效日历或更新时间');
 let previous='';
 for(const session of value.sessions){
  if(!object(session)||!date(session.date)||!instant(session.close_at)||session.date<=previous)return unavailable('择时交易日历无效');
  previous=session.date;
 }
 const rowIssue=(r,warmup=false)=>{
  if(!object(r)||!date(r.date)||!Number.isFinite(r.close)||r.close<=0)return '价格或交易日期无效';
  if(warmup&&r.eligible===false)return r.ma200===null?null:'暖机状态无效';
  if(r.eligible!==true)return '缺少完整收盘数据';
  if(['ma200','prior_ma200','ma5','r5','volatility','threshold','deviation','trend_change'].some(k=>!Number.isFinite(r[k]))||['ma200','prior_ma200','ma5'].some(k=>r[k]<=0)||r.volatility<0||(r.multiple!==null&&!Number.isFinite(r.multiple)))return '指标缺失或不是有限数值';
  if(['trend','near','conflict','start_known'].some(k=>typeof r[k]!=='boolean')||![null,'A','B'].includes(r.kind)||!Number.isInteger(r.consecutive)||r.consecutive<0||(r.kind&&r.consecutive<1)||(r.first_date!==null&&(!date(r.first_date)||r.first_date>r.date))||(r.kind&&r.start_known&&r.first_date===null))return '信号或连续性字段无效';
  return null;
 };
 const indices={};
 for(const [key,symbol] of Object.entries({sp500:'SPX',ndx:'NDX'})){
  const item=value.indices[key];let error=null;
  if(!object(item))error='指数槽位缺失';
  else if(item.symbol!==symbol)error='指数身份不匹配：应为'+symbol;
  else if(item.error!=null&&typeof item.error!=='string')error='数据状态字段无效';
  else if(item.latest==null){indices[key]={symbol,error:item.error??'无可用数据'};continue;}
  else error=!instant(item.successful_at)?'最后成功时间无效':rowIssue(item.latest);
  if(error){indices[key]={symbol,error:'数据无效：'+error};continue;}
  const h=item.history;
  let historyError=null;
  if(h!=null){
   if(!object(h)||h.schema_version!==1||h.strategy!==value.strategy||h.symbol!==symbol||!Array.isArray(h.rows)||!h.rows.length||!Array.isArray(h.sessions)||h.sessions.length!==h.rows.length||!instant(h.generated_at)||typeof h.source!=='string'||!h.source||typeof h.source_sha256!=='string'||!/^[a-f0-9]{64}$/.test(h.source_sha256))historyError='历史版本、来源或交易日序列无效';
   else{
    let previous='',last=null;
    for(let i=0;i<h.rows.length;i++){
     const r=h.rows[i];
     if(rowIssue(r,true)||r.date<=previous||r.date!==h.sessions[i]){historyError='历史价格无效或缺失交易日，不能确认连续性';break;}
     if(r.eligible&&r.kind&&r.consecutive!==(last?.eligible&&last.kind?last.consecutive+1:1)){historyError='历史连续计数无效';break;}
     if(r.eligible&&r.kind&&last?.eligible&&last.kind&&r.first_date!==last.first_date){historyError='历史轮次首次日期不一致';break;}
     previous=r.date;last=r;
    }
    if(!historyError&&(h.price_start!==h.rows[0].date||h.price_end!==h.rows.at(-1).date||h.price_end!==item.latest.date||h.eligible_start!==(h.rows.find(r=>r.eligible)?.date??null)))historyError='历史覆盖日期与当前数据不一致';
   }
  }
  indices[key]=historyError?{...item,history:undefined,history_error:historyError}:item;
 }
 return {...value,preview_notice:typeof value.preview_notice==='string'?value.preview_notice:undefined,indices};
}

export function timingStatus(data,item,now=Date.now()){
 if(!data)return {title:'正在读取',current:false};
 const sessions=data.sessions?.filter(s=>Date.parse(s.close_at)<=now),expected=sessions?.at(-1)?.date??data.expected_date;
 const calendarValid=!!data.calendar_until&&new Date(now).toISOString().slice(0,10)<=data.calendar_until;
 if(!item?.latest)return {title:'暂不可判定',reason:item?.error??data.error??'无可用数据',expected,current:false};
 if(!calendarValid)return {title:'历史结果',reason:'交易日历覆盖不足，暂不可确认新鲜度',expected,current:false};
 if(item.latest.date===expected&&!item.error)return {title:item.latest.kind?item.latest.kind+'类进场信号':item.latest.trend?'当前条件未满足':'长期趋势不满足',reason:'数据完整',expected,current:true};
 const close=sessions?.at(-1)?.close_at;
 let due=Date.parse(data.due_at);
 if(close){const date=new Date(Date.parse(close)+8*3600000).toISOString().slice(0,10);due=Date.parse(date+'T07:00:00+08:00');if(due<Date.parse(close))due+=86400000;}
 const waiting=now<due;
 return {title:waiting?'等待更新／历史结果':'历史结果',reason:waiting?'等待本次07:00更新':item.error??'最新数据未到／更新失败',expected,current:false};
}

// Display grouping only: strategy flags and point-in-time counters are never recomputed here.
export function historyView(history,range='3',type='AB',allDates=false){
 if(!history)return {rows:[],signals:[],markers:[]};
 let round=null;
 const full=history.rows.map(r=>{if(r.eligible&&r.kind){if(r.consecutive===1||round===null)round=r.date;return {...r,roundId:round};}round=null;return r;});
 const end=full.at(-1).date,cutoff=new Date(end+'T00:00:00Z');cutoff.setUTCFullYear(cutoff.getUTCFullYear()-Number(range));
 const start=range==='all'?full[0].date:cutoff.toISOString().slice(0,10);
 const rows=full.filter(r=>r.date>=start),signals=rows.filter(r=>r.eligible&&r.kind&&(type==='AB'||r.kind===type));
 const seen=new Set();
 const markers=allDates?signals:signals.filter(r=>{if(seen.has(r.roundId))return false;seen.add(r.roundId);return true;});
 return {rows,signals,markers:markers.map(r=>({...r,continuation:r.consecutive>1||!r.start_known})),ongoingRound:full.at(-1).kind?full.at(-1).roundId:null};
}
