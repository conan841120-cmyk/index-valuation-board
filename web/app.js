/* 指数估值日报 · 前端（视觉方向 B：财经数据新闻版面，用户 2026-09-27 选定）
   数据全部来自 window.DASHBOARD；页面只做视图变换，统计量由 Python 侧算好。 */
(function () {
  'use strict';
  var D = window.DASHBOARD;
  var C = {ink:'#14100C', dim:'#6A6156', faint:'#C9BFB0', red:'#8A1F12', indigo:'#2E4A6B',
           olive:'#5C6B45', rule:'#DED6C8', grid:'#EAE3D6', area:'rgba(46,74,107,0.15)',
           areaEdge:'#8FA6BB', bandD:'rgba(138,31,18,0.07)', bandC:'rgba(92,107,69,0.09)'};
  var state = {key:null, win:null, metricKey:null, view:'metric', tab:'stats', ma:0,
               lines:{std1:false, mean:false}, thr:{}};
  var chart = null, minis = {};

  function idx(){ return D.indices.filter(function(i){return i.key===state.key;})[0]; }
  function fmt(v,d){ return v===null||v===undefined?'—':Number(v).toFixed(d===undefined?2:d); }
  function grp(v){ if(v===null||v===undefined) return '—'; return Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
  function slice(data, win){ var v=data.views&&data.views[win]; var start=v?v.start:0;
    return {points:data.series.slice(start), views:v||{pct:[],z:[]}}; }
  function metricData(){
    var i = idx(), alt = (i.alternates||{})[state.metricKey];
    var data = Object.assign({}, alt || i);
    data.is_alternate = !!alt;
    data.metric_key = alt ? state.metricKey : (i.metric_key || i.metric);
    data.metric_label = data.metric_label || data.label || data.metric;
    data.value_meta = data.value_meta || {};
    data.data_date = data.data_date || (data.series.length ? data.series[data.series.length-1].date : null);
    data.source = data.source || data.value_meta.source || null;
    return data;
  }
  function sourceName(key){
    var names={danjuan:'蛋卷（雪球系）',csindex:'中证指数官方',csindex_tr:'中证全收益指数',
      csindex_perf:'中证指数行情','csindex-perf':'中证官方市盈率',official:'中证官方估值',tencent:'腾讯行情',derived:'≈ 推导估算'};
    return names[key] || key || '—';
  }
  function levelDate(data, i){
    var last=data.series[data.series.length-1] || {};
    return data.is_alternate ? (last.level_date || '—') : (i.level_date || '—');
  }
  function windowLabel(win){ return win==='ALL'?(state.metricKey==='official_dy'?'全部已积累':'全部可用'):win; }
  function defaultPcts(data){ return data.direction==='inverse'
    ? {danger:20, median:50, opportunity:80} : {danger:80, median:50, opportunity:20}; }
  function thresholdPcts(data){ return state.thr[thrKey()] || defaultPcts(data); }
  function validPcts(p, inverse){ return inverse ? p.danger<p.median && p.median<p.opportunity
    : p.opportunity<p.median && p.median<p.danger; }
  function zoneFor(data, s, t){
    if(!t.custom) return s.zone;
    var p=s.percentile, q=t.pcts;
    return data.direction==='inverse'
      ? (p>=q.opportunity?'低估':p>=q.median?'合理偏低':p>=q.danger?'合理偏高':'高估')
      : (p<q.opportunity?'低估':p<q.median?'合理偏低':p<q.danger?'合理偏高':'高估');
  }
  function thrKey(){ return state.key+':'+state.metricKey; }

  /* 阈值：默认取 Python 侧算好的分位值；点 ⚙ 可自定义分位（只影响本页显示） */
  function thresholds(data, s, win){
    var over = state.thr[thrKey()];
    if(!over){ return {danger:s.danger, median:s.median, opportunity:s.opportunity, custom:false,
                      pcts:defaultPcts(data)}; }
    var vals = slice(data, win).points.map(function(p){return p.value;}).sort(function(a,b){return a-b;});
    var q = function(p){ var k = Math.floor(p/100*vals.length); k = Math.max(0, Math.min(vals.length-1, k)); return vals[k]; };
    return {danger:q(over.danger), median:q(over.median), opportunity:q(over.opportunity), custom:true, pcts:over};
  }

  /* ------------------------------------------------ 控件条 */
  function renderControls(){
    var i = idx(), data = metricData();
    var rg = document.getElementById('ranges'); rg.innerHTML='';
    D.windows.forEach(function(w){
      if(!data.stats[w]) return;
      var b=document.createElement('span'); b.className='chip mono'; b.textContent = windowLabel(w);
      b.setAttribute('aria-current', w===state.win?'true':'false');
      b.onclick=function(){ state.win=w; renderAll(); }; rg.appendChild(b);
    });
    var mg = document.getElementById('metrics'); mg.innerHTML='';
    [['pe','市盈率TTM'],['pb','市净率LF'],['dy','股息率'],['rp','风险溢价'],['ps','市销率TTM'],['pcf','市现率TTM']]
      .forEach(function(m){
        var avail = (m[0]===(i.metric_key||i.metric)) || !!(i.alternates||{})[m[0]];
        var b=document.createElement('span'); b.className='chip mono'; b.textContent=m[1];
        b.setAttribute('aria-current', m[0]===state.metricKey?'true':'false');
        if(!avail){ b.style.opacity=0.45; b.style.cursor='not-allowed';
          b.title='免费数据源没有该口径的历史序列'; }
        else { b.title = (m[0]===(i.metric_key||i.metric))? '该指数主口径' : '查看该数据源独立序列';
          b.onclick=function(){ state.metricKey=m[0]; renderAll(); }; }
        mg.appendChild(b);
      });
    Object.keys(i.alternates||{}).filter(function(k){
      return ['pe','pb','dy','rp','ps','pcf'].indexOf(k)<0;
    }).forEach(function(k){
      var alt=i.alternates[k], b=document.createElement('span');
      b.className='chip mono'; b.textContent=alt.label || alt.metric_label || k;
      b.setAttribute('aria-current', k===state.metricKey?'true':'false');
      b.title='独立真实对照区间，不与推导历史拼接';
      b.onclick=function(){ state.metricKey=k; if(alt.recommended_window) state.win=alt.recommended_window; renderAll(); }; mg.appendChild(b);
    });
    var vw = document.getElementById('views'); vw.innerHTML='';
    [['metric','指标'],['percentile','分位点'],['std','标准差']].forEach(function(v){
      var b=document.createElement('span'); b.className='chip mono'; b.textContent=v[1];
      b.setAttribute('aria-current', v[0]===state.view?'true':'false');
      b.onclick=function(){ state.view=v[0]; renderAll(); }; vw.appendChild(b);
    });
    document.getElementById('btnStats').className = 'btn mono'+(state.tab==='stats'?' on':'');
    document.getElementById('btnDetail').className = 'btn mono'+(state.tab==='detail'?' on':'');
  }

  /* ------------------------------------------------ 标题行与判断句 */
  function renderLead(){
    var i = idx(), data = metricData(), s = data.stats[state.win], t = thresholds(data, s, state.win);
    document.getElementById('leadName').textContent = i.name;
    document.getElementById('leadCode').textContent = i.code+'　·　'+data.metric_label+
      (data.direction==='inverse'?'（越高越便宜）':'（越高越贵）')+(data.flag==='derived'?'　·　≈ 推导估算':(data.is_alternate?'　·　独立真实序列':''));
    document.getElementById('leadPrice').textContent = '最新行情点位 '+grp(i.latest_level)+'（'+(i.latest_level_date||'—')+'）　'+
      (i.change_pct===null||i.change_pct===undefined?'—':(i.change_pct>0?'▲ +':(i.change_pct<0?'▼ ':'　'))+fmt(Math.abs(i.change_pct))+'%')+'　最新涨跌日期 '+(i.change_date||'—')+
      '　｜　估值图对应点位 '+grp(s.level)+'　该序列点位日期 '+levelDate(data,i);
    var inv = data.direction==='inverse';
    var nearDanger = inv ? (s.current-t.danger) : (t.danger-s.current);
    var toChance = inv ? (t.opportunity-s.current) : (s.current-t.opportunity);
    var zone=zoneFor(data,s,t), cls = zone==='低估'?'cold':(zone==='高估'?'hot':'');
    var line = data.metric_label+' 处在「<span class="'+cls+'">'+zone+'</span>」区间：当前值 '+
      fmt(s.current,data.digits)+'，'+windowLabel(state.win)+'分位点 <b>'+fmt(s.percentile)+'%</b>。';
    line += toChance>=0 ? ' 距机会值还差 '+fmt(Math.abs(toChance),data.digits)+'。'
                        : ' 已越过机会值 '+fmt(Math.abs(toChance),data.digits)+'。';
    line += nearDanger>=0 ? ' 距危险值还有 '+fmt(Math.abs(nearDanger),data.digits)+'。'
                          : ' 已越过危险值 '+fmt(Math.abs(nearDanger),data.digits)+'。';
    if(t.custom){ line += ' <span class="flag">自定义分位阈值：危险 '+t.pcts.danger+' / 中位 '+t.pcts.median+' / 机会 '+t.pcts.opportunity+'</span>'; }
    document.getElementById('stance').innerHTML = line;
    return {i:i, data:data, s:s, t:t};
  }

  /* ------------------------------------------------ 读数表 + 编者注 */
  var READ_ROWS = [['current','当前值'],['percentile','分位点'],['danger','危险值'],['median','中位数'],
                   ['opportunity','机会值'],['level','指数点位'],['maxmin','最大值 / 最小值'],
                   ['meanstd','平均值 · σ'],['zscore','z 分数']];
  function renderReadout(ctx){
    var i = ctx.i, data = ctx.data, s = ctx.s, t = ctx.t;
    var unit = (data.metric==='pe'||data.metric==='pb')?' ×':' %';
    var approx = data.flag==='derived';
    var el = document.getElementById('readTable');
    var vals = {
      current: fmt(s.current,data.digits)+unit,
      percentile: fmt(s.percentile)+' %',
      danger: fmt(t.danger,data.digits),
      median: fmt(t.median,data.digits),
      opportunity: fmt(t.opportunity,data.digits),
      level: grp(s.level),
      maxmin: fmt(s.max,data.digits)+' / '+fmt(s.min,data.digits),
      meanstd: fmt(s.mean,data.digits)+' · '+fmt(s.std,data.digits),
      zscore: fmt(s.zscore)
    };
    var html = '<caption>读数　'+data.metric_label+'　·　'+(windowLabel(state.win))+
      '　·　n = '+s.n+'</caption>';
    READ_ROWS.forEach(function(r){
      var key=r[0], label=r[1], gear='', flag='';
      if(key==='danger'||key==='median'||key==='opportunity'){
        gear=' <span class="gear" data-thr="'+key+'" title="自定义分位阈值">⚙</span>';
      }
      if(approx && key!=='level'){
        flag=' <span class="flag" title="推导估算，历史会随当期锚点修订">≈</span>';
      }
      html += '<tr><td>'+label+gear+flag+'</td><td class="mono">'+vals[key]+'</td></tr>';
    });
    el.innerHTML = html;
    Array.prototype.forEach.call(el.querySelectorAll('[data-thr]'), function(node){
      node.onclick = function(){
        var which = node.getAttribute('data-thr');
        var cur = thresholdPcts(data);
        var label = {danger:'危险值', median:'中位数', opportunity:'机会值'}[which];
        var ans = window.prompt('把「'+label+'」改成第几分位？（0-100，留空恢复整组默认值；'+
          (data.direction==='inverse'?'危险 < 中位 < 机会':'机会 < 中位 < 危险')+'）', cur[which]);
        if(ans===null) return;
        ans = ans.trim();
        if(ans===''){ delete state.thr[thrKey()]; }
        else {
          var v = Number(ans), next = Object.assign({}, cur);
          if(!isFinite(v) || v<0 || v>100){ window.alert('请输入 0-100 之间的数字'); return; }
          next[which] = v;
          if(!validPcts(next,data.direction==='inverse')){
            window.alert(data.direction==='inverse'?'须满足 危险 < 中位 < 机会':'须满足 机会 < 中位 < 危险'); return;
          }
          state.thr[thrKey()] = next;
        }
        renderAll();
      };
    });

    var notes = [], meta=data.value_meta || {}, anchor=meta.anchor_observation || {};
    if(data.flag==='derived'){
      notes.push('<span class="flag">≈</span> <b>股息率历史为推导估算</b>（'+(meta.method||'锚定推导')+
        '）：当前值 '+fmt(s.current,data.digits)+'%，'+(meta.current_is_observed?'当期为观测锚值':'当期仍为估算值')+
        '。锚点来源 '+sourceName(anchor.source||data.source)+'，日期 '+(anchor.date||'—')+'，值 '+fmt(anchor.value,data.digits)+
        '%；近端校准 '+((meta.calibration||{}).applied?'已应用':'未应用')+'。当期锚点估算会修订历史，不能视为当时可获得的数据。');
    } else if(data.is_alternate){
      notes.push('<b>当前显示「'+data.metric_label+'」独立真实对照</b>（'+data.series.length+' 个周频点，来源 '+
        sourceName(data.source)+'）：仅覆盖 '+(data.series[0]?data.series[0].date:'—')+' → '+data.data_date+
        ' 的真实区间，'+(data.metric_key==='official_dy'?
        '不与主股息率的推导历史拼接。点上方股息率按钮可切回主口径。':'与其他指标分开计算。'));
    } else if(data.flag==='partial'){
      notes.push('<span class="flag">!</span> <b>真实市盈率仅自 '+(meta.daily_first_date||'—')+' 起</b>：'+
        '更早区间不做推算；周频首点 '+(meta.weekly_first_date||'—')+'，分位点只反映该真实区间。');
    } else {
      notes.push('估值序列来自 '+sourceName(data.source)+' 的真实数据；不同平台的数据源、统计与采样口径可能有差异。');
    }
    if((i.level_series||[]).some(function(q){return q.date>data.data_date;})){
      notes.push('估值按周频展示；估值截止后的价格线按腾讯日线延伸。暂无估值的日期留空，不参与估值统计。');
    }
    if(data.threshold_buffer && !data.is_alternate){
      notes.push('<b>阈值附近的观察缓冲区</b>：指标视图中的红、绿阴影分别围绕危险值、机会值，'+
        '上下各为对应阈值的 '+fmt(data.threshold_buffer*100,0)+'%。宽度为人为设定，只作接近阈值时的视觉提醒，'+
        '不代表统计误差或置信区间；阈值及区间判断仍按原公式计算。');
    }
    var pcts=t.pcts;
    notes.push('当前'+windowLabel(state.win)+'窗口阈值：危险第 '+pcts.danger+' 分位、中位第 '+pcts.median+
      ' 分位、机会第 '+pcts.opportunity+' 分位；阈值取升序第 ⌊pn⌋ 项（末端截断）。'+
      '分位点 = 小于当前值的样本占比；图中历史排名为当前整个窗口的事后排名，不能直接用于回测。'+
      'z 分数 = (当前值 − 平均值) / 样本标准差。');
    document.getElementById('notes').innerHTML = notes.join('<br><br>');
  }

  /* ------------------------------------------------ 图表 */
  function movingAverage(arr, n){
    var out=[], sum=0, q=[];
    for(var i=0;i<arr.length;i++){ var v=arr[i]; q.push(v); sum+=v; if(q.length>n){ sum-=q.shift(); }
      out.push(q.length===n? +(sum/n).toFixed(4): null); }
    return out;
  }
  function payload(){
    var i = idx(), data = metricData(), sl = slice(data, state.win), s = data.stats[state.win];
    var t = thresholds(data, s, state.win);
    var main, label;
    if(state.view==='percentile'){ main = sl.views.pct.slice(0, sl.points.length); label='分位点（%）'; }
    else if(state.view==='std'){ main = sl.views.z.slice(0, sl.points.length); label='z 分数（标准差倍数）'; }
    else {
      main = sl.points.map(function(p){return p.value;});
      label = data.metric_label;
      if(state.ma>0){ main = movingAverage(main, state.ma); label = data.metric_label+'（'+state.ma+' 周均）'; }
    }
    return {i:i, data:data, s:s, t:t, view:state.view, pts:sl.points, main:main, label:label};
  }
  /* 点位轴：显式取整范围，让「调仓三角」永远贴在图表底边（各指数一致） */
  function niceStep(raw){
    var set=[1,1.5,2,2.5,3,4,5,6,8,10];
    if(!(raw>0)) return 1;
    var mag=Math.pow(10,Math.floor(Math.log(raw)/Math.LN10)), norm=raw/mag;
    for(var k=0;k<set.length;k++){ if(norm<=set[k]) return set[k]*mag; }
    return 10*mag;
  }
  function levelAxis(levels){
    var nums=levels.filter(function(v){return v!==null&&v!==undefined&&isFinite(v);});
    if(!nums.length) return {min:null, max:null, step:null};
    var lo=Math.min.apply(null,nums), hi=Math.max.apply(null,nums);
    if(lo===hi) hi=lo+1;
    var step=niceStep((hi-lo)/4);
    return {min:Math.floor(lo/step)*step, max:Math.ceil(hi/step)*step, step:step};
  }

  function baseOption(p, small){
    var points = p.pts.slice(), main = p.main.slice();
    var valuationEnd = points.length ? points[points.length-1].date : null;
    (p.i.level_series || []).forEach(function(q){
      if(valuationEnd && q.date>valuationEnd){
        points.push({date:q.date, value:null, level:q.value}); main.push(null);
      }
    });
    var dates = points.map(function(x){return x.date;});
    var times = dates.map(function(d){return Date.parse(d+'T00:00:00Z');});
    var levels = points.map(function(x){return x.level;});
    /* 日期是交易日标签；统一用UTC午夜定位，周频与日频共享真实时间比例。 */
    var spanYears = (times[times.length-1] - times[0]) / 3.15576e10;
    function fmtLabel(v){ return new Date(v).toISOString().slice(2,7); }
    var mark = {silent:true, symbol:'none', label:{show:false}, data:[]};
    var add = function(y, color, dash){ if(y===null||y===undefined) return;
      mark.data.push({yAxis:y, lineStyle:{color:color,type:dash?'dashed':'solid',width:1.1}, label:{show:false}}); };
    if(p.view==='metric'){
      add(p.t.danger, C.red, true); add(p.t.median, C.dim, true); add(p.t.opportunity, C.olive, true);
      if(state.lines.mean) add(p.s.mean, C.faint, true);
      if(state.lines.std1){ add(p.s.std_plus, C.faint, true); add(p.s.std_minus, C.faint, true); }
    } else if(p.view==='percentile'){
      var over = thresholdPcts(p.data);
      add(over.danger, C.red, true); add(over.median, C.dim, true); add(over.opportunity, C.olive, true);
    } else {
      add(2, C.faint, true); add(1, p.data.direction==='inverse'?C.olive:C.red, true); add(0, C.dim, true); add(-1, p.data.direction==='inverse'?C.red:C.olive, true); add(-2, C.faint, true);
    }
    var area = {silent:true, data:[]};
    var band = p.view==='metric' && !p.data.is_alternate ? p.data.threshold_buffer : null;
    if(band){
      area.data.push([{yAxis:p.t.danger*(1-band), itemStyle:{color:C.bandD}},{yAxis:p.t.danger*(1+band)}]);
      area.data.push([{yAxis:p.t.opportunity*(1-band), itemStyle:{color:C.bandC}},{yAxis:p.t.opportunity*(1+band)}]);
    }
    var ax = levelAxis(levels);
    /* 调仓标志：落在真实存在的周频点上，贴住图表底边（y = 点位轴最小值，符号上移半个高度） */
    var reb = [];
    (p.i.rebalance_dates||[]).forEach(function(d){
      if(d < dates[0]) { return; }
      for(var k=0;k<dates.length;k++){
        if(dates[k] >= d){ reb.push([times[k], ax.min]); break; }
      }
    });
    return {
      animation:false,
      useUTC:true,
      grid: small?{left:2,right:2,top:6,bottom:16}:{left:48,right:52,top:10,bottom:30},
      tooltip: small?{show:false}:{trigger:'axis',backgroundColor:'rgba(247,243,236,0.97)',borderColor:C.rule,
        textStyle:{color:C.ink,fontSize:12,fontFamily:'Menlo, monospace'},
        formatter:function(ps){ if(!ps.length) return ''; var k=ps[0].dataIndex, q=points[k];
          var vw = p.data.views && p.data.views[state.win];
          var pct = vw && vw.pct ? vw.pct[k] : null;
          return q.date+'<br>'+p.data.metric_label+(p.data.flag==='derived'?' ≈ 推导估算':'')+' '+
            (q.value===null?'暂无估值数据（估值截止 '+valuationEnd+'）':fmt(q.value,p.data.digits))+
            (pct!==null&&pct!==undefined?'<br>分位点 '+fmt(pct)+'%':'')+
            (q.level!==null&&q.level!==undefined?'<br>点位 '+grp(q.level):''); }},
      xAxis:{type:'time',min:times[0],max:times[times.length-1],boundaryGap:[0,0],
        splitNumber:small?2:Math.max(2,Math.ceil(spanYears*(spanYears>4?2:4))),
        axisLine:{lineStyle:{color: small?C.rule:C.dim}},
        axisTick: small?{show:false}:{show:true, length:3, lineStyle:{color:C.faint}},
        axisLabel: small
          ? {show:true, formatter:fmtLabel, hideOverlap:true,
             color:C.faint, fontSize:9, fontFamily:'Menlo, monospace'}
          : {show:true, formatter:fmtLabel, color:C.dim, fontSize:10.5,
             fontFamily:'Menlo, monospace', hideOverlap:true}},
      yAxis:[
        {type:'value',scale:true,splitNumber: small?2:4,axisLine:{show:false},axisTick:{show:false},
         axisLabel: small?{show:false}:{color:C.dim,fontSize:10.5,fontFamily:'Menlo, monospace',
           formatter:function(v){return Number(v.toFixed(Math.abs(v)<10?2:0));}},
         splitLine:{show:!small,lineStyle:{color:C.grid}}},
        {type:'value',scale:true,splitNumber:4,position:'right',
         min:ax.min, max:ax.max, interval:ax.step,
         axisLine:{show:false},axisTick:{show:false},
         axisLabel: small?{show:false}:{color:C.dim,fontSize:10.5,fontFamily:'Menlo, monospace',
           formatter:function(v){return Number(Math.round(v)).toLocaleString('en-US');}},
         splitLine:{show:false}}
      ],
      series:[
        {type:'line',data:main.map(function(v,k){return [times[k],v];}),symbol:'none',z:2,connectNulls:false,lineStyle:{color:C.areaEdge,width:1},
         areaStyle:{color:C.area,origin:'start'},markLine:mark,markArea:area},
        {type:'line',data:levels.map(function(v,k){return [times[k],v];}),symbol:'none',yAxisIndex:1,z:3,lineStyle:{color:C.indigo,width:1}},
        {type:'scatter',data:reb,symbol:'triangle',symbolSize:6,yAxisIndex:1,symbolOffset:[0,-5],
         itemStyle:{color:C.red},silent:true,z:4}
      ]
    };
  }
  function renderChart(){
    var p = payload();
    if(!chart){ chart = echarts.init(document.getElementById('chart')); }
    chart.setOption(baseOption(p, false), true);
    chart.resize();
  }

  /* ------------------------------------------------ 图例（可点开均线/标准差） */
  function renderLegend(){
    var i = idx(), data = metricData();
    var t = thresholds(data, data.stats[state.win], state.win);
    var el = document.getElementById('legend');
    var items = [];
    items.push({t:'dot', c:C.areaEdge,
      label: state.view==='metric' ? (state.ma>0? data.metric_label+'（'+state.ma+' 周均）' : data.metric_label)
           : (state.view==='percentile'? '分位点' : 'z 分数')});
    if(data.flag==='derived') items[0].label+=' ≈ 推导估算';
    items.push({t:'bar', c:C.indigo, label:'指数点位'});
    if(i.rebalance_dates && i.rebalance_dates.length){ items.push({t:'tri', label:'调仓标志'}); }
    if(state.view==='metric'){
      items.push({t:'dash', c:C.red, label:'危险值 '+fmt(t.danger,data.digits)});
      items.push({t:'dash', c:C.dim, label:'中位数 '+fmt(t.median,data.digits)});
      items.push({t:'dash', c:C.olive, label:'机会值 '+fmt(t.opportunity,data.digits)});
      if(data.threshold_buffer && !data.is_alternate){
        items.push({t:'band', c:C.bandD, label:'危险值观察缓冲区'});
        items.push({t:'band', c:C.bandC, label:'机会值观察缓冲区'});
      }
    } else if(state.view==='percentile'){
      var over = thresholdPcts(data);
      items.push({t:'dash', c:C.red, label:'危险 '+over.danger+'%'});
      items.push({t:'dash', c:C.dim, label:'中位 '+over.median+'%'});
      items.push({t:'dash', c:C.olive, label:'机会 '+over.opportunity+'%'});
    } else {
      items.push({t:'dash', c:C.red, label:data.direction==='inverse'?'−1σ':'+1σ'});
      items.push({t:'dash', c:C.dim, label:'0（均值）'});
      items.push({t:'dash', c:C.olive, label:data.direction==='inverse'?'+1σ':'−1σ'});
    }
    var off = [{t:'dash', c:C.faint, label:'标准差(±1)', k:'std1'}, {t:'dash', c:C.faint, label:'平均值', k:'mean'}];
    function html(it, dim){
      var mark = it.t==='dot' ? '<span class="dot" style="background:'+it.c+'"></span>'
        : it.t==='bar' ? '<span class="bar" style="border-color:'+it.c+'"></span>'
        : it.t==='dash' ? '<span class="dash" style="border-color:'+it.c+'"></span>'
        : it.t==='band' ? '<span style="display:inline-block;width:14px;height:10px;background:'+it.c+'"></span>'
        : '<span class="tri"></span>';
      return '<span'+(it.k?' data-k="'+it.k+'"':'')+(dim?' class="off"':'')+'>'+mark+it.label+'</span>';
    }
    el.innerHTML = items.map(function(it){return html(it,false);}).join('') +
      off.map(function(it){ return html(it, !state.lines[it.k]); }).join('');
    Array.prototype.forEach.call(el.querySelectorAll('[data-k]'), function(node){
      node.onclick = function(){
        var k = node.getAttribute('data-k');
        state.lines[k] = !state.lines[k];
        renderChart(); renderLegend();
      };
    });
  }

  /* ------------------------------------------------ 明细数据 */
  function renderDetail(){
    var data = metricData(), sl = slice(data, state.win), rows='', n=0;
    for(var k=sl.points.length-1; k>=0 && n<240; k--, n++){
      var q = sl.points[k], pct = sl.views.pct? sl.views.pct[k] : null;
      rows += '<tr><td class="mono">'+q.date+'</td><td class="mono">'+fmt(q.value,data.digits)+'</td>'+
        '<td class="mono">'+(pct===null||pct===undefined?'—':fmt(pct)+'%')+'</td>'+
        '<td class="mono">'+grp(q.level)+'</td></tr>';
    }
    document.getElementById('detail').innerHTML =
      '<table class="dt"><thead><tr><th>日期（周频）</th><th>'+data.metric_label+'</th><th>分位点</th>'+
      '<th>指数点位</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }

  /* ------------------------------------------------ 小倍数（五个指数并置） */
  function renderMultiples(){
    var el = document.getElementById('multiples'); el.innerHTML='';
    Object.keys(minis).forEach(function(k){ try{ minis[k].dispose(); }catch(e){} });
    minis = {};
    D.indices.forEach(function(i){
      var win = i.stats[state.win] ? state.win : (i.recommended_window || D.default_window);
      var data = {series:i.series, views:i.views, metric:i.metric, metric_label:i.metric_label,
                  digits:i.digits, direction:i.direction, flag:i.flag};
      var sl = slice(data, win), s = i.stats[win];
      var card = document.createElement('div');
      card.className='card';
      card.setAttribute('aria-current', i.key===state.key?'true':'false');
      var unit = (i.metric==='pe'||i.metric==='pb')?' ×':' %';
      card.innerHTML = '<div class="n">'+i.name+'</div><div class="c mono">'+i.code+'　'+i.metric_label+(i.flag==='derived'?' ≈':'')+
        '　'+(win==='ALL'?'全部可用':win)+' · 默认阈值</div><div class="mini"></div>'+
        '<div class="r"><span>分位点 <b>'+fmt(s.percentile)+'%</b>　<b>'+s.zone+'</b></span>'+
        '<span><b>'+fmt(s.current,i.digits)+unit+'</b></span></div>';
      card.onclick = function(){
        state.key=i.key; state.metricKey=i.metric_key||i.metric;
        state.win = i.stats[state.win]? state.win : win;
        renderAll();
      };
      el.appendChild(card);
      var c = echarts.init(card.querySelector('.mini'));
      c.setOption(baseOption({i:i, data:data, s:s,
        t:{danger:s.danger, median:s.median, opportunity:s.opportunity}, view:'metric',
        pts:sl.points, main:sl.points.map(function(p){return p.value;}), label:i.metric_label}, true), true);
      minis[i.key] = c;
    });
  }

  /* ------------------------------------------------ 页脚 */
  function watchStatus(){
    function stamp(v){ v=(v||'').replace(' ','T');
      return Date.parse(v && !/(Z|[+-]\d{2}:?\d{2})$/.test(v)?v+'+08:00':v); }
    var w=D.rule_watch || {}, checked=stamp(w.checked_at), generated=stamp(D.generated_at);
    var fresh=isFinite(checked)&&isFinite(generated)&&checked>=generated-86400000;
    var matched=Array.isArray(w.matched)?w.matched.length:w.matched,
      missing=Array.isArray(w.missing)?w.missing.length:w.missing;
    var ok=w.state==='consistent' && matched===5 && missing===0 && fresh && !!w.article_date;
    var label=ok?'该篇文章的 5 项指标口径一致（未核验数值）'
      : w.state==='mismatch'?'指标口径不一致'
      : !fresh?'检测缺失或已过期，不能确认一致'
      : w.state==='failed'?'检测失败，不能确认一致':'检测不完整，不能确认一致';
    return {ok:ok, label:label, watch:w};
  }
  function renderColophon(ctx){
    var i=ctx.i, data=ctx.data, s=ctx.s, ws=watchStatus(), w=ws.watch;
    var statuses=i.source_status || D.source_status || {}, statusLines=[];
    Object.keys(statuses).forEach(function(k){
      var status=statuses[k]; if(!status) return;
      statusLines.push(sourceName(k)+'：'+(status.ok===false?(status.fallback===false?'抓取失败，无有效旧缓存':'抓取失败，沿用旧数据'):status.fallback?'使用备用/缓存数据':status.ok===true?'抓取成功':'抓取状态未记录')+
        (status.freshness==='lagging'?'，估值数据滞后（已取得行情截止 '+status.reference_date+'）'
          :status.freshness==='aligned'?'；估值与已取得行情日期一致'
          :status.freshness==='unknown'?'；估值新鲜度无法核验':'')+
        '；尝试 '+(status.at||'—')+'；上次成功 '+(status.last_success_at||'—')+'；数据日期 '+(status.last_data_date||'未记录'));
    });
    document.getElementById('colophonLeft').innerHTML =
      '口径核对：'+(w.article_date||'未知日期')+' 文章 · 检测 '+(w.checked_at||'—')+' · '+ws.label+'。<br>'+
      '估值来源：'+sourceName(data.source)+'　｜　估值截止 <em>'+(data.data_date||'—')+'</em>　｜　窗口：'+
      windowLabel(state.win)+'（周频，'+s.n+' 个点）。<br>'+statusLines.join('<br>')+(statusLines.length?'<br>':'')+
      '本页为个人研究复刻，<em>不构成投资建议</em>。';
    document.getElementById('colophonRight').innerHTML = '区间 '+s.start+' → '+s.end+
      '<br>该序列点位日期 '+levelDate(data,i)+' · 最新涨跌日期 '+(i.change_date||'—')+'<br>页面生成 '+D.generated_at;
  }

  /* ------------------------------------------------ 总装 */
  function renderAll(){
    if(!state.key) state.key = D.indices[0].key;
    var i = idx();
    if(!state.metricKey) state.metricKey = i.metric_key||i.metric;
    else if(state.metricKey!==(i.metric_key||i.metric) && !(i.alternates||{})[state.metricKey]) state.metricKey = i.metric_key||i.metric;
    var selected=metricData();
    if(!state.win || !selected.stats[state.win]){
      state.win=selected.stats[selected.recommended_window]?selected.recommended_window
        : selected.stats[D.default_window]?D.default_window
        : D.windows.filter(function(w){return !!selected.stats[w];})[0];
    }
    var ws=watchStatus(), data=metricData();
    document.getElementById('alert').innerHTML = ws.ok?'':'<div class="alarm">⚠ '+ws.label+
      '（文章 '+(ws.watch.article_date||'—')+'，检测 '+(ws.watch.checked_at||'—')+'）。</div>';
    if(['NDX.GI','SPX.GI'].includes(i.code) && data.data_date && i.change_date && data.data_date<i.change_date){
      document.getElementById('alert').innerHTML += '<div class="alarm">估值与最新行情日期不同：估值截止 '+
        data.data_date+'，涨跌行情截止 '+i.change_date+'。页面更新不代表估值源已更新；不使用价格推算新市盈率。</div>';
    }
    document.getElementById('mastMeta').innerHTML =
      '估值截止 <b>'+(data.data_date||'—')+'</b><br>周频 · '+D.indices.length+' 个指数 · 页面生成 <b>'+D.generated_at+'</b>';
    var rail = document.getElementById('rail'); rail.innerHTML='';
    D.indices.forEach(function(x){
      var b=document.createElement('button');
      b.setAttribute('aria-current', x.key===state.key?'true':'false');
      b.innerHTML = x.name+'<span class="code mono">'+x.code+'</span>';
      b.onclick = function(){
        state.key=x.key; state.metricKey=x.metric_key||x.metric;
        state.win=x.recommended_window||D.default_window; renderAll();
      };
      rail.appendChild(b);
    });
    renderControls();
    var ctx = renderLead();
    renderReadout(ctx);
    renderChart(); renderLegend(); renderColophon(ctx); renderMultiples();
    var statsView = state.tab==='stats';
    document.getElementById('chart').style.display = statsView?'block':'none';
    document.getElementById('legend').style.display = statsView?'flex':'none';
    document.getElementById('detail').style.display = statsView?'none':'block';
    if(!statsView) renderDetail();
  }

  function exportCsv(){
    var i = idx(), data = metricData(), sl = slice(data, state.win);
    var lines = ['date,metric,value,percentile,level,window,ranks_basis,kind,series_kind,source,value_date,level_date'];
    function csv(v){ return '"'+String(v===null||v===undefined?'':v).replace(/"/g,'""')+'"'; }
    sl.points.forEach(function(p,k){
      var pct = sl.views.pct? sl.views.pct[k] : '';
      lines.push([p.date,data.metric_key,p.value,pct,p.level,state.win,'当前整个窗口事后排名；不可直接回测',
        p.kind || data.flag || 'unknown',data.flag || 'unknown',p.source || data.source,p.value_date || p.date,p.level_date || ''].map(csv).join(','));
    });
    var blob = new Blob(['\ufeff'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = i.name+'_'+data.metric_label+'_'+state.win+'.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function init(){
    var q = {};
    location.search.replace(/^\?/,'').split('&').forEach(function(kv){
      if(!kv) return; var parts = kv.split('=');
      q[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]||'');
    });
    var target = D.indices.filter(function(x){return x.key===q.index;})[0] || D.indices[0];
    state.key = target.key;
    state.win = (q.window && target.stats[q.window]) ? q.window : (target.recommended_window || D.default_window);
    state.metricKey = q.metric || target.metric_key || target.metric;
    state.view = q.view || 'metric';
    state.tab = q.tab || 'stats';
    if(q.lines==='all'){ state.lines = {std1:true, mean:true}; }
    document.getElementById('ma').onchange = function(e){ state.ma = Number(e.target.value); renderChart(); renderLegend(); };
    document.getElementById('btnStats').onclick = function(){ state.tab='stats'; renderAll(); };
    document.getElementById('btnDetail').onclick = function(){ state.tab='detail'; renderAll(); };
    document.getElementById('btnExport').onclick = exportCsv;
    window.addEventListener('resize', function(){
      if(chart) chart.resize();
      Object.keys(minis).forEach(function(k){ minis[k].resize(); });
    });
    renderAll();
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
