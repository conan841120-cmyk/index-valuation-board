(function(){
  'use strict';
  const labels={healthy:'正常',partial:'部分可用',unavailable:'不可用',unknown:'待核验',ok:'可用',empty:'空响应',failed:'获取失败',stale:'过期',invalid_time:'时间待核验',invalid_basis:'报价口径待核验',not_checked:'本轮未检查',degraded:'降级',success:'完成'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label=v=>labels[v]||v||'待核验';
  function safeURL(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}}
  function time(value,zone='Asia/Shanghai'){
    if(!value)return '未知';
    if(/^\d{4}-\d{2}-\d{2}$/.test(value))return value+'（仅日期）';
    if(!/(Z|[+-]\d{2}:?\d{2})$/.test(value))return value+'（时间待核验）';
    const d=new Date(value.replace(/([+-]\d{2})(\d{2})$/,'$1:$2'));return Number.isNaN(d.getTime())?'时间待核验':new Intl.DateTimeFormat('zh-CN',{timeZone:zone,dateStyle:'short',timeStyle:'medium',hourCycle:'h23'}).format(d);
  }
  function runs(day){return [...(day?.digest||[]),...(day?.alerts||[]),...(day?.quotes||[])].sort((a,b)=>a.started_at.localeCompare(b.started_at));}
  function preferred(day){return runs(day).at(-1);}
  const indices=['^GSPC','^IXIC','^DJI','SPY','QQQ','DIA','IWM','VIX'];
  const bonds=['^TNX','^TYX','TLT','GLD','USO'];
  function parseSymbols(text){
    const symbols=[...new Set(text.toUpperCase().split(/[\s,，、;；]+/).filter(Boolean))];
    const invalid=symbols.filter(symbol=>!/[A-Z0-9]/.test(symbol)||!/^[\^A-Z0-9.\-]{1,10}$/.test(symbol));
    if(invalid.length)throw new Error('代码格式无效：'+invalid.join('、')+'。请使用不超过 10 位的字母、数字、点、横线或 ^。');
    if(symbols.length>100)throw new Error('自选清单最多 100 个代码。');
    const fixed=symbols.filter(symbol=>indices.includes(symbol)||bonds.includes(symbol));
    if(fixed.length)throw new Error(fixed.join('、')+' 已在固定市场 / 美债栏目中，无需加入自选。');
    return symbols;
  }
  function defaultSymbols(run){return Object.keys(run?.quotes||{}).filter(symbol=>!indices.includes(symbol)&&!bonds.includes(symbol));}
  function configURL(symbols,revision){
    if(!/^[a-f0-9]{64}$/.test(revision||''))throw new Error('尚未取得云端配置版本，请刷新网页后再提交。');
    const url=new URL('https://github.com/conan841120-cmyk/us-trader-daily/issues/new');
    url.searchParams.set('title','[美股配置] 更新自选代码');
    url.searchParams.set('body','US_MARKET_WATCHLIST_V1\n'+JSON.stringify({base_revision:revision,symbols:parseSymbols(symbols.join(' '))}));
    return url.href;
  }
  const names={'^GSPC':'标普500','^IXIC':'纳斯达克综合','^DJI':'道琼斯','SPY':'标普500 ETF','QQQ':'纳指100 ETF','DIA':'道指 ETF','IWM':'罗素2000 ETF','VIX':'VIX','^TNX':'10年美债收益率','^TYX':'30年美债收益率','TLT':'长债 ETF','GLD':'黄金 ETF','USO':'原油 ETF'};
  function quotes(data,symbols){
    const rows=symbols.map(symbol=>{
      const q=data[symbol];if(!q)return `<tr><td>${esc(names[symbol]||symbol)}</td><td colspan="3">行情缺失</td></tr>`;
      const valid=q.data_status==='ok'&&typeof q.price==='number'&&Number.isFinite(q.price);
      const price=valid?q.price.toLocaleString('zh-CN',{maximumFractionDigits:2})+(symbol==='^TNX'||symbol==='^TYX'?'%':''):'—';
      const yieldQuote=symbol==='^TNX'||symbol==='^TYX';
      const delta=yieldQuote&&typeof q.prev==='number'?(q.price-q.prev)*100:q.pct;
      const change=valid&&typeof delta==='number'&&Number.isFinite(delta)?(delta>=0?'+':'')+delta.toFixed(yieldQuote?1:2)+(yieldQuote?' bp':'%'):'—';
      const type={previous_close:'最近已完成交易日收盘',intraday:'盘中行情快照',session_snapshot:'交易日行情（仅日期）',closing_snapshot:'收市附近行情快照',yield_snapshot:'收益率快照'}[q.quote_phase]||(q.kind==='daily'?'日线收盘参考':'行情快照');
      const fallback=(q.fallback_from?`<div class="muted">备用源接替 ${esc(q.fallback_from)}：${esc(label(q.fallback_reason))}</div>`:'')+(q.prev_basis==='last_minus_change'?'<div class="muted">昨收基准由同条报价的点数变动校验</div>':'');
      return `<tr><td>${esc(names[symbol]||symbol)}<div class="muted">${esc(symbol)}</div></td><td class="num">${esc(price)}<br>${esc(change)}</td><td>${esc(q.source||'未知')}<div class="muted">${esc(type)}</div>${fallback}</td><td>${q.trade_date?`交易日 ${esc(q.trade_date)}<br>`:''}${esc(time(q.as_of))}<div class="badge">${esc(label(q.data_status))}</div>${q.expected_close_date?`<div class="muted">应有收盘 ${esc(q.expected_close_date)}</div>`:''}</td></tr>`;
    });
    return rows.length?`<div class="table-wrap"><table><thead><tr><th>标的</th><th>点位 / 涨跌</th><th>来源与类型</th><th>数据时间（北京） / 状态</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>`:'<p class="empty">本批次没有行情快照。</p>';
  }
  function articles(items,empty){return items.length?items.map(item=>{
    const url=safeURL(item.link),title=esc(item.title_zh||item.title||'未命名条目');
    const points=(item.points||[]).filter(p=>typeof p==='string');
    return `<article><h3>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`:title}</h3><p class="meta">${esc(item.source||'来源未知')} · 发布 ${esc(time(item.published))}${typeof item.score==='number'?' · 筛选评分 '+esc(item.score):''}</p>${item.title_zh?`<p class="muted">原题：${esc(item.title)}</p>`:''}${item.zh?`<p>标题 / 信源摘要：${esc(item.zh)}</p>`:''}${points.length?`<p class="muted">核验正文要点</p><ul>${points.map(p=>'<li>'+esc(p)+'</li>').join('')}</ul>`:'<p class="muted">未取得核验正文要点；如有摘要，仅依据标题 / 信源摘要。</p>'}</article>`;
  }).join(''):`<p class="empty">${esc(empty)}</p>`;}
  function sourceTable(sources){return `<div class="table-wrap"><table><thead><tr><th>来源 / 类型</th><th>采集时状态</th><th>可用 / 收到</th><th>检查时间（北京）</th><th>最后数据时间（北京）</th></tr></thead><tbody>${sources.map(row=>`<tr><td>${esc(row.name)}<div class="muted">${esc({news:'新闻',quote:'行情',discussion:'讨论'}[row.kind]||row.kind)}</div></td><td>${esc(label(row.status))}</td><td class="num">${esc(row.usable??0)} / ${esc(row.received??0)}</td><td>${esc(time(row.checked_at))}</td><td>${esc(time(row.latest_published_at))}</td></tr>`).join('')}</tbody></table></div>`;}
  function watchlist(symbols,data,cloud){
    return `<details id="other-quotes" open><summary>其他关注行情（${symbols.length} 项）</summary><form id="watchlist-form" class="watchlist-editor"><label for="watchlist-input">自选代码（逗号、空格或换行分隔；最多 100 项）</label><textarea id="watchlist-input" rows="3" spellcheck="false" placeholder="例如：NVDA, AAPL, BRK.B">${esc(symbols.join(', '))}</textarea><button type="submit" ${cloud?'':'disabled'}>提交云端配置</button><a id="cloud-request" hidden target="_blank" rel="noopener noreferrer">打开 GitHub 确认页</a><p class="muted">${cloud?'输入或删除代码后提交，在 GitHub 登录并点击“Create”（创建）确认；仅仓库所有者可修改。提交记录自动关闭表示云端保存成功，随后等待网页同步，刷新本页查看已生效清单。配置冲突或失败时记录保持打开，请先刷新本页，再重新提交。':'云端配置尚未交接，暂不能提交。'}</p><p class="muted">云端保存后，后续定时任务按新清单采集；未取得行情的代码显示“行情缺失”。当前行情仍是所选历史批次。市场 / 美债固定栏目和旧存档保留。清空后提交会停止其他自选代码的后续采集。</p><p id="watchlist-status" role="status" aria-live="polite"></p></form>${symbols.length?quotes(data,symbols):'<p class="empty">自选清单为空；输入代码并提交即可添加。</p>'}</details>`;
  }
  function freshness(run,publication,now=Date.now()){
    if(!publication.latest)return '';
    const schedule=publication.schedule||[];
    if(!schedule.length)return '<p class="muted">尚无交易日历，无法自动核验是否漏更。</p>';
    const last=schedule.at(-1);
    if(now>new Date(last.close).getTime()+86400000)return '<p>交易日历覆盖已到期，请查看云端任务是否持续运行。</p>';
    const completed=schedule.filter(row=>new Date(row.close).getTime()<=now).at(-1);
    if(!completed)return '';
    const missing=['^GSPC','SPY','QQQ'].filter(symbol=>{
      const q=run.quotes?.[symbol];return !q||q.data_status!=='ok'||(q.trade_date||q.as_of?.slice(0,10)||'')<completed.date;
    });
    if(missing.length)return `<p><strong>行情更新待检查：</strong>应有 ${esc(completed.date)} 交易日收盘，${esc(missing.join('、'))} 尚未取得合格数据。可在来源状态或云端任务中查看失败与补抓结果。</p>`;
    const current=schedule.find(row=>new Date(row.open).getTime()<=now&&new Date(row.close).getTime()>now);
    if(current&&new Date(run.finished_at).getTime()<new Date(current.open).getTime())return '<p>美股已开盘；当前仍展示上一交易日快照，盘中数据尚未更新。</p>';
    return '';
  }
  function report(run,day,watchSymbols=defaultSymbols(run),cloud=null,publication={}){
    if(!run)return '<p class="empty">尚无已完成的公开存档。首次交接后可在这里按日期回看。</p><section>'+watchlist(watchSymbols,{},cloud)+'</section>';
    const newsRun=run.mode==='quotes'?(day.digest||[]).at(-1)||{}:run;
    const ready=(newsRun.sources||[]).some(row=>row.kind==='news'&&row.status==='ok');
    const news=[...(newsRun.news||[])].sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0));
    const ticker=news.filter(row=>['ticker-news','sec-filing'].includes(row.category)).slice(0,10);
    const events=(day.alerts||[]).filter(row=>row.price_alerts?.length||row.heads?.length||row.news?.length);
    const latestAlert=(day.alerts||[]).at(-1);
    const other=watchSymbols;
    return `<div class="banner ${run.data_status==='healthy'&&run.status==='success'?'':'warn'}"><strong>${esc(label(run.data_status))} · ${{digest:'日报',alerts:'预警快照',quotes:'独立收盘行情'}[run.mode]||'行情快照'}</strong><p>采集开始：${esc(time(run.started_at))}（北京） / ${esc(time(run.started_at,'America/New_York'))}（美东）<br>完成：${esc(time(run.finished_at))}（北京）</p><p class="meta">运行：${esc(run.status==='failed'?'失败':label(run.status))} · ${esc(run.run_id)} · AI 摘要：${esc(run.ai_status==='ok'?'已生成':run.ai_status==='degraded'?'降级，可能只有原标题':'本批次未记录')}</p>${publication.published_at?`<p class="meta">页面发布：${esc(time(publication.published_at))}（北京）</p>`:''}${freshness(run,publication)}<p>当前展示历史快照；下方“可用”按采集时点判断，不代表实时行情。</p>${latestAlert?`<p class="meta">当天最近预警检查：${esc(time(latestAlert.started_at))} · ${esc(label(latestAlert.data_status))}。可切换批次查看，数据不足不能推断无异动。</p>`:''}</div>
    <section><div class="grid"><div><h2>市场快照</h2>${quotes(run.quotes||{},indices)}</div><div><h2>美债与避险资产</h2>${quotes(run.quotes||{},bonds)}</div></div>${watchlist(other,run.quotes||{},cloud)}</section>
    <section><h2>${run.mode==='alerts'?'本轮选中快讯':'重要事件'}</h2>${run.mode==='quotes'?`<p class="muted">新闻来自最近日报：${esc(time(newsRun.started_at))}（北京）。行情采集不等待新闻或 AI。</p>`:''}<p class="muted">自动筛选与摘要，评分是信息筛选分，不是买卖信号。</p>${articles(news.slice(0,12),ready?'本批次没有选中条目，不代表全市场没有事件。':'新闻来源缺失、过期或为空，无法判断是否存在重要事件。')}</section>
    <section><h2>自选股动态</h2>${articles(ticker,ready?'本批次没有选中自选股动态。':'新闻数据不足，无法判断自选股动态。')}</section>
    <section><h2>当天预警检测记录</h2><p class="muted">这里记录检测结果，不代表通知已送达；空记录也不能证明全市场无异动。</p>${events.length?events.map(row=>`<details open><summary>${esc(time(row.started_at))} · ${esc(label(row.data_status))}</summary><ul>${[...(row.price_alerts||[]).map(a=>a.text),...(row.heads||[])].map(v=>'<li>'+esc(v)+'</li>').join('')}</ul>${articles(row.news||[],'此轮没有选中快讯。')}</details>`).join(''):'<p class="empty">当天尚无已存档的选中事件。</p>'}</section>
    <section><details id="source-status"><summary><h2>来源与数据状态</h2></summary><p class="muted">检查时间是请求时点；最后数据时间是文章发布时间或报价时点。仅日期报价无法证明分钟级新鲜度。</p>${sourceTable(run.sources||[])}</details></section>`;
  }
  const API={freshness,esc,safeURL,time,runs,preferred,quotes,articles,report,parseSymbols,defaultSymbols,configURL};
  if(typeof module!=='undefined')module.exports=API;
  if(typeof document==='undefined')return;
  const boot=window.US_MARKET_BOOTSTRAP,dates=boot.manifest.dates;
  const dateSelect=document.getElementById('date'),runSelect=document.getElementById('run'),status=document.getElementById('load-status'),download=document.getElementById('download');
  const cloud=boot.manifest.watchlist;
  let day=boot.day,request=0;
  const watchSymbols=cloud?.symbols??defaultSymbols(preferred(day));
  const cache=new Map(day?[[day.date,day]]:[]);
  dateSelect.innerHTML=dates.map(date=>`<option value="${esc(date)}">${esc(date)}</option>`).join('');
  function paint(){
    const selected=runs(day).find(row=>row.run_id===runSelect.value);
    document.getElementById('report').innerHTML=report(selected,day||{},watchSymbols,cloud,{published_at:boot.published_at,schedule:boot.manifest.market_schedule,latest:dateSelect.value===dates[0]});
    download.hidden=!selected;
    if(selected)download.href='reports/'+encodeURIComponent(selected.run_id)+'.md';
  }
  function setDay(value){
    day=value;
    runSelect.innerHTML=runs(day).map(row=>`<option value="${esc(row.run_id)}">${{digest:'日报',alerts:'预警',quotes:'收盘行情'}[row.mode]||'快照'} · ${esc(time(row.started_at))} · ${esc(label(row.data_status))}</option>`).join('');
    const picked=preferred(day);if(picked)runSelect.value=picked.run_id;
    paint();
  }
  async function selectDate(){
    const date=dateSelect.value,ticket=++request;
    status.textContent='正在读取 '+date+' 存档…';runSelect.disabled=true;download.hidden=true;
    runSelect.innerHTML='';
    // 不把旧日期的内容留在新日期控件下面。
    document.getElementById('report').innerHTML='';
    try{
      let value=cache.get(date);
      if(!value){const response=await fetch('data/'+encodeURIComponent(date)+'.json',{cache:'no-cache'});if(!response.ok)throw new Error('HTTP '+response.status);value=await response.json();if(value.schema_version!==1||value.date!==date||!Array.isArray(value.digest)||!Array.isArray(value.alerts)||(value.quotes!==undefined&&!Array.isArray(value.quotes)))throw new Error('存档格式异常');cache.set(date,value);}
      if(ticket!==request)return;setDay(value);status.textContent='';runSelect.disabled=false;
      const url=new URL(location.href);url.searchParams.set('date',date);history.replaceState(null,'',url);
    }catch(error){if(ticket!==request)return;status.textContent='该日期存档未能读取：'+error.message+'。请重新选择日期或刷新；不能据此判断无事件。';}
  }
  dateSelect.addEventListener('change',selectDate);runSelect.addEventListener('change',paint);
  document.getElementById('report').addEventListener('submit',event=>{
    if(event.target.id!=='watchlist-form')return;
    event.preventDefault();
    try{
      const url=configURL(parseSymbols(document.getElementById('watchlist-input').value),cloud?.revision);
      const link=document.getElementById('cloud-request');link.href=url;link.hidden=false;
      window.open(url,'_blank','noopener,noreferrer');
      document.getElementById('watchlist-status').textContent='尚未保存：请在新打开的 GitHub 页面确认提交。若没有弹出新页面，点击上方“打开 GitHub 确认页”。';
    }catch(error){document.getElementById('watchlist-status').textContent=error.message;}
  });
  if(!dates.length){dateSelect.disabled=true;runSelect.disabled=true;setDay(null);return;}
  const chosen=new URL(location.href).searchParams.get('date');dateSelect.value=dates.includes(chosen)?chosen:dates[0];
  selectDate();
})();
