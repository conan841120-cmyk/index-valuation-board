/* 月度宏观指标：计算在 Python 完成；缺失值不在浏览器中填补。 */
(function () {
  'use strict';
  var factors=['retail','ppi','hk_m2','credit_impulse'];
  var labels=['社零同比','PPI同比','香港广义货币同比','信用脉冲'];
  var colors=['#2478a4','#cd7545','#449877','#9366ad'];
  function fmt(v,d){return v===null||v===undefined?'—':Number(v).toFixed(d===undefined?4:d);}
  function escape(s){return String(s===null||s===undefined?'—':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function gaps(rows){
    var result=[],previous=null;
    rows.forEach(function(row,index){
      if(row.leading_indicator===null)return;
      if(previous&&index-previous.index>1)result.push([{coord:[previous.row.date,previous.row.leading_indicator]},{coord:[row.date,row.leading_indicator]}]);
      previous={row:row,index:index};
    });return result;
  }
  function select(rows,months){return months==='ALL'?rows:rows.slice(-Number(months));}
  var csvColumns=['date','leading_indicator','hsi_close','retail_yoy','ppi_yoy','hk_m2_yoy','credit_impulse_3m',
    'z_retail','z_ppi','z_hk_m2','z_credit_impulse','contribution_retail','contribution_ppi','contribution_hk_m2','contribution_credit_impulse',
    'gdp_quarter','gdp_2q','retail_release_date','ppi_release_date','m2_release_date','social_financing_release_date','gdp_release_date'];
  function csv(rows){return csvColumns.join(',')+'\n'+rows.map(function(row){return csvColumns.map(function(k){return row[k]===null||row[k]===undefined?'':row[k];}).join(',');}).join('\n');}
  function roundWindow(r){return r?escape(r.window_start)+'<br>至 '+escape(r.window_end):'—';}
  function roundTable(sources){
    var statuses={acquired:'已取得本轮数据',scheduled:'尚未进入本轮窗口',awaiting:'本轮尚未取得，窗口内每日检查',catch_up:'本轮超期未取得，每日追踪'};
    return '<caption>本次与下次抓取安排（发布窗口）</caption><thead><tr><th>数据</th><th>本次抓取区间</th><th>本次目标数据</th><th>本轮数据状态</th><th>下次抓取区间</th><th>下次目标数据</th></tr></thead><tbody>'+sources.map(function(s){
      var r=s.current_round,n=s.next_round;
      return '<tr><td>'+escape(s.label)+'</td><td>'+roundWindow(r)+'</td><td>'+escape(r&&r.observation_period)+(s.dataset==='retail'&&r&&r.observation_period.endsWith('-02')?'<span class="macro-round-note">核验1—2月合并公告</span>':'')+'</td><td>'+escape(r&&statuses[r.status])+
        (s.backlog_rounds||[]).map(function(b){return '<span class="macro-round-note macro-warning">旧轮次待补：'+escape(b.observation_period)+'（原区间 '+escape(b.window_start)+' 至 '+escape(b.window_end)+'），每日追踪</span>';}).join('')+
        (s.last_probe_error?'<span class="macro-round-note macro-warning">最近轻量检查失败：'+escape(s.last_probe_error)+'</span>':'')+'</td><td>'+roundWindow(n)+'</td><td>'+escape(n&&n.observation_period)+'</td></tr>';
    }).join('')+'</tbody>';
  }
  function mainOption(rows){
    return {animation:false,color:['#243e50','#bd864d'],grid:{left:58,right:65,top:25,bottom:65},
      tooltip:{trigger:'axis',formatter:function(params){
        var date=params[0].axisValue,row=rows.find(function(r){return r.date===date;});
        return escape(date)+'<br>领先指标：'+(row.leading_indicator===null?'缺失（虚线仅为历史连接）':fmt(row.leading_indicator))+'<br>恒生指数：'+fmt(row.hsi_close,2);
      }},
      xAxis:{type:'category',data:rows.map(function(r){return r.date;}),boundaryGap:false,axisLabel:{hideOverlap:true}},
      yAxis:[{type:'value',name:'领先指标',min:function(v){return Math.min(-2.5,Math.floor(v.min*2)/2);},max:function(v){return Math.max(2,Math.ceil(v.max*2)/2);},splitLine:{lineStyle:{color:'#EAE3D6'}}},
        {type:'value',name:'恒生指数（点）',min:function(v){return Math.min(12000,Math.floor(v.min/2000)*2000);},max:function(v){return Math.max(36000,Math.ceil(v.max/2000)*2000);},splitLine:{show:false}}],
      dataZoom:[{type:'inside'},{type:'slider',height:17,bottom:10}],
      series:[{name:'领先指标',type:'line',data:rows.map(function(r){return r.leading_indicator;}),connectNulls:false,showSymbol:false,lineStyle:{width:2},
        markLine:{silent:true,symbol:['none','none'],label:{show:false},tooltip:{show:false},lineStyle:{type:'dashed',color:'#243e50',width:2},data:gaps(rows)}},
        {name:'恒生指数',type:'line',yAxisIndex:1,data:rows.map(function(r){return r.hsi_close;}),connectNulls:false,showSymbol:false,lineStyle:{width:1.5}}]};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={gaps:gaps,select:select,csv:csv,mainOption:mainOption,roundTable:roundTable};
  if(typeof document==='undefined')return;
  var D=window.HSI_MACRO,root=document.getElementById('hsi-macro');
  if(!D){root.hidden=true;return;}
  var latest=D.latest,previous=D.previous,chart=echarts.init(document.getElementById('macro-chart'));
  var contribution=echarts.init(document.getElementById('macro-contribution-chart'));
  document.getElementById('macro-update').textContent='生成时间 '+D.generated_at.replace('T',' ').replace('+08:00','（北京时间）');
  var delta=previous&&previous.leading_indicator!==null?latest.leading_indicator-previous.leading_indicator:null;
  var degraded=D.sources.filter(function(s){return s.state==='cached';});
  document.getElementById('macro-summary').innerHTML='<span>最新有效月份 <b>'+escape(latest.date)+'</b></span><span>指标 <b>'+fmt(latest.leading_indicator)+'</b></span><span>上月变化 <b>'+(delta===null?'—':(delta>=0?'+':'')+fmt(delta))+'</b></span><span>缺失月份 '+D.missing_months+' 个'+(degraded.length?' · <span class="macro-warning">'+degraded.length+' 项抓取失败，沿用缓存</span>':'')+'</span>';
  document.getElementById('macro-latest-components').innerHTML='<caption>最新有效月份 '+escape(latest.date)+'</caption><thead><tr><td>组件</td><td>原始值</td><td>标准分</td><td>贡献</td><td>月度变化</td></tr></thead><tbody>'+factors.map(function(name,i){
    var raw=name==='credit_impulse'?latest.credit_impulse_3m*100:latest[name+'_yoy'];
    var change=previous&&previous['contribution_'+name]!==null?latest['contribution_'+name]-previous['contribution_'+name]:null;
    return '<tr><td>'+labels[i]+'</td><td>'+fmt(raw,2)+'%</td><td>'+fmt(latest['z_'+name],3)+'</td><td>'+fmt(latest['contribution_'+name],4)+'</td><td>'+fmt(change,4)+'</td></tr>';
  }).join('')+'</tbody>';
  var monitor=D.monitor||{sources:[],alerts:[]};
  var watched={};monitor.sources.forEach(function(s){watched[s.dataset]=s;});
  var warnings=monitor.sources.filter(function(s){return s.last_probe_error;});
  var pending=monitor.sources.filter(function(s){return s.phase==='catch_up';});
  document.getElementById('macro-monitor').innerHTML='<p>估值日报每日08:30更新；本指标在各来源发布窗口内每日18:30检查，有新数据才重算（北京时间，云端执行可能延迟）。</p>'+
    monitor.alerts.map(function(a){return '<p class="macro-warning" role="alert">报警：'+escape(a.message)+'</p>';}).join('')+
    pending.map(function(s){return '<p>'+escape(s.label)+'仍缺 '+escape(s.missing_periods.join('、'))+'，已转为每日追踪。</p>';}).join('')+
    (warnings.length?'<p class="macro-warning">'+warnings.map(function(s){return escape(s.label);}).join('、')+'最近轻量检查失败；已有数据保留，详情见来源表。</p>':'');
  var windows=monitor.sources.map(function(s){return escape(s.label)+'：'+escape(s.window)+(s.dataset==='gdp'?'（仅1、4、7、10月）':s.dataset==='retail'?'（2月无独立发布轮次）':'');});
  document.getElementById('macro-methods').innerHTML=D.methods.map(function(s){return '<p>'+escape(s)+'</p>';}).join('')+'<p>发布窗口：'+windows.join('；')+'。窗口结束仍未取得数据则每天继续检查，进入下一轮仍缺上一轮时报警，补齐后解除。社零1—2月合并公告不填补独立月度值。</p><p>成功检查不等于重新抓取，也不表示出现新月份；生成时间不等于数据月份。仅检查近期数据与新公告，历史静默修订可手动强制刷新核对。</p>';
  document.getElementById('macro-methods').innerHTML+='<p>本次指最近已开启的发布轮次；下一轮窗口开始时自动切换，本轮成功后仍保留结果。旧轮次缺口单独保留，不因切换消失。区间是计划检查窗口，目标数据是经济观察期；日期安排按北京时间在每次页面生成时更新。恒指仅随宏观更新作为对照，不设独立发布轮次。</p>';
  document.getElementById('macro-round-table').innerHTML=roundTable(monitor.sources);
  var states={fresh:'最近下载成功',cached:'最近下载失败，沿用缓存',retained:'本次未下载，沿用已有数据',snapshot:'历史快照（未联网刷新）'};
  document.getElementById('macro-source-table').innerHTML='<caption>官方来源与下载记录（下载成功不代表本轮目标数据已取得）</caption><thead><tr><th>数据</th><th>官方字段／来源</th><th>最新观察期</th><th>公布日期</th><th>最近下载结果</th><th>最近成功抓取</th><th>最近轻量检查</th></tr></thead><tbody>'+D.sources.map(function(s){var check=watched[s.dataset]||{};return '<tr><td>'+escape(s.label)+'</td><td><a href="'+escape(s.url)+'" target="_blank" rel="noopener">'+escape(s.official_field)+'</a></td><td>'+escape(s.latest_observation)+'</td><td>'+escape(s.release_date)+'</td><td title="'+escape(s.error||'')+'">'+escape(states[s.state]||s.state)+'</td><td>'+escape(s.last_success_at)+'</td><td title="'+escape(check.last_probe_error||'')+'">'+escape(check.last_checked_at)+'</td></tr>';}).join('')+'</tbody>';
  var failures=(D.release_lookup_status||[]).filter(function(s){return s.state==='cached';});
  if(failures.length)document.getElementById('macro-methods').innerHTML+='<p class="macro-warning">部分公布日期本次核验失败，保留已有日期；未知日期不推测。</p>';
  function render(){
    var rows=select(D.series,document.getElementById('macro-range').value);
    chart.setOption(mainOption(rows),true);
    contribution.setOption({animation:false,color:colors,grid:{left:50,right:35,top:35,bottom:30},legend:{textStyle:{fontSize:11}},tooltip:{trigger:'axis'},
      xAxis:{type:'category',data:rows.map(function(r){return r.date;}),boundaryGap:false,axisLabel:{hideOverlap:true}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#EAE3D6'}}},
      series:factors.map(function(name,i){return {name:labels[i],type:'line',showSymbol:false,connectNulls:false,data:rows.map(function(r){return r['contribution_'+name];})};})},true);
    document.getElementById('macro-detail-table').innerHTML='<thead><tr><th>观察月份</th><th>领先指标</th><th>恒生指数（点）</th><th>社零同比（%）</th><th>PPI同比（%）</th><th>香港广义货币同比（%）</th><th>信用脉冲（%）</th></tr></thead><tbody>'+rows.slice().reverse().map(function(r){return '<tr><td>'+escape(r.date)+'</td><td>'+fmt(r.leading_indicator)+'</td><td>'+fmt(r.hsi_close,2)+'</td><td>'+fmt(r.retail_yoy,2)+'</td><td>'+fmt(r.ppi_yoy,2)+'</td><td>'+fmt(r.hk_m2_yoy,2)+'</td><td>'+fmt(r.credit_impulse_3m===null?null:100*r.credit_impulse_3m,2)+'</td></tr>';}).join('')+'</tbody>';
  }
  document.getElementById('macro-range').onchange=render;
  document.getElementById('macro-export').onclick=function(){var rows=select(D.series,document.getElementById('macro-range').value),url=URL.createObjectURL(new Blob(['\uFEFF'+csv(rows)],{type:'text/csv;charset=utf-8'}));var a=document.createElement('a');a.href=url;a.download='恒生领先指标-'+rows[0].date+'-'+rows[rows.length-1].date+'.csv';a.click();setTimeout(function(){URL.revokeObjectURL(url);},1000);};
  window.addEventListener('resize',function(){chart.resize();contribution.resize();});
  render();
}());
