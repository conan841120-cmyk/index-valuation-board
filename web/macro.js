/* 月度宏观指标：计算在 Python 完成；缺失值不在浏览器中填补。 */
(function () {
  'use strict';
  var factors=['retail','ppi','hk_m2','credit_impulse'];
  var labels=['社零同比','出厂价格同比','香港广义货币同比','信用脉冲'];
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
  if(typeof module!=='undefined'&&module.exports)module.exports={gaps:gaps,select:select,csv:csv,mainOption:mainOption};
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
  document.getElementById('macro-methods').innerHTML=D.methods.map(function(s){return '<p>'+escape(s)+'</p>';}).join('')+'<p>云端每日名义更新时刻为北京时间08:30；执行可能延迟。成功抓取不表示有新月份公布，生成时间也不等于数据月份。</p>';
  var states={fresh:'本次抓取成功',cached:'抓取失败，沿用缓存',snapshot:'历史快照（未联网刷新）'};
  document.getElementById('macro-source-table').innerHTML='<thead><tr><th>数据</th><th>官方字段／来源</th><th>最新观察期</th><th>公布日期</th><th>抓取状态</th><th>最近成功抓取</th></tr></thead><tbody>'+D.sources.map(function(s){return '<tr><td>'+escape(s.label)+'</td><td><a href="'+escape(s.url)+'" target="_blank" rel="noopener">'+escape(s.official_field)+'</a></td><td>'+escape(s.latest_observation)+'</td><td>'+escape(s.release_date)+'</td><td title="'+escape(s.error||'')+'">'+escape(states[s.state]||s.state)+'</td><td>'+escape(s.last_success_at)+'</td></tr>';}).join('')+'</tbody>';
  var failures=(D.release_lookup_status||[]).filter(function(s){return s.state==='cached';});
  if(failures.length)document.getElementById('macro-methods').innerHTML+='<p class="macro-warning">部分公布日期本次核验失败，保留已有日期；未知日期不推测。</p>';
  function render(){
    var rows=select(D.series,document.getElementById('macro-range').value);
    chart.setOption(mainOption(rows),true);
    contribution.setOption({animation:false,color:colors,grid:{left:50,right:15,top:35,bottom:30},legend:{textStyle:{fontSize:11}},tooltip:{trigger:'axis'},
      xAxis:{type:'category',data:rows.map(function(r){return r.date;}),boundaryGap:false,axisLabel:{hideOverlap:true}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#EAE3D6'}}},
      series:factors.map(function(name,i){return {name:labels[i],type:'line',showSymbol:false,connectNulls:false,data:rows.map(function(r){return r['contribution_'+name];})};})},true);
    document.getElementById('macro-detail-table').innerHTML='<thead><tr><th>观察月份</th><th>领先指标</th><th>恒生指数（点）</th><th>社零同比（%）</th><th>出厂价格同比（%）</th><th>香港广义货币同比（%）</th><th>信用脉冲（%）</th></tr></thead><tbody>'+rows.slice().reverse().map(function(r){return '<tr><td>'+escape(r.date)+'</td><td>'+fmt(r.leading_indicator)+'</td><td>'+fmt(r.hsi_close,2)+'</td><td>'+fmt(r.retail_yoy,2)+'</td><td>'+fmt(r.ppi_yoy,2)+'</td><td>'+fmt(r.hk_m2_yoy,2)+'</td><td>'+fmt(r.credit_impulse_3m===null?null:100*r.credit_impulse_3m,2)+'</td></tr>';}).join('')+'</tbody>';
  }
  document.getElementById('macro-range').onchange=render;
  document.getElementById('macro-export').onclick=function(){var rows=select(D.series,document.getElementById('macro-range').value),url=URL.createObjectURL(new Blob(['\uFEFF'+csv(rows)],{type:'text/csv;charset=utf-8'}));var a=document.createElement('a');a.href=url;a.download='恒生领先指标-'+rows[0].date+'-'+rows[rows.length-1].date+'.csv';a.click();setTimeout(function(){URL.revokeObjectURL(url);},1000);};
  window.addEventListener('resize',function(){chart.resize();contribution.resize();});
  render();
}());
