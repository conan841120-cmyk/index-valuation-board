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
  function grp(v){ return Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
  function slice(data, win){ var v=data.views&&data.views[win]; var start=v?v.start:0;
    return {points:data.series.slice(start), views:v||{pct:[],z:[]}}; }
  function metricData(){
    var i = idx();
    if(state.metricKey && state.metricKey!==i.metric && i.alternates[state.metricKey]){
      var alt = i.alternates[state.metricKey]; alt.is_alternate = true; alt.metric_key = state.metricKey; return alt;
    }
    i.is_alternate = false; i.metric_key = i.metric; return i;
  }
  function thrKey(){ return state.key+':'+state.metricKey; }

  /* 阈值：默认取 Python 侧算好的分位值；点 ⚙ 可自定义分位（只影响本页显示） */
  function thresholds(data, s, win){
    var over = state.thr[thrKey()];
    if(!over){ return {danger:s.danger, median:s.median, opportunity:s.opportunity, custom:false}; }
    var vals = slice(data, win).points.map(function(p){return p.value;}).sort(function(a,b){return a-b;});
    var q = function(p){ var k = Math.floor(p/100*vals.length); k = Math.max(0, Math.min(vals.length-1, k)); return vals[k]; };
    var inv = data.direction === 'inverse';
    return {danger: inv? q(over.opportunity): q(over.danger), median: q(over.median),
            opportunity: inv? q(over.danger): q(over.opportunity), custom:true, pcts:over};
  }

  /* ------------------------------------------------ 控件条 */
  function renderControls(){
    var i = idx(), data = metricData();
    var rg = document.getElementById('ranges'); rg.innerHTML='';
    D.windows.forEach(function(w){
      if(!data.stats[w]) return;
      var b=document.createElement('span'); b.className='chip mono'; b.textContent = w==='ALL'?'上市以来':w;
      b.setAttribute('aria-current', w===state.win?'true':'false');
      b.onclick=function(){ state.win=w; renderAll(); }; rg.appendChild(b);
    });
    var mg = document.getElementById('metrics'); mg.innerHTML='';
    [['pe','市盈率TTM'],['pb','市净率LF'],['dy','股息率'],['rp','风险溢价'],['ps','市销率TTM'],['pcf','市现率TTM']]
      .forEach(function(m){
        var avail = (m[0]===i.metric) || !!i.alternates[m[0]];
        var b=document.createElement('span'); b.className='chip mono'; b.textContent=m[1];
        b.setAttribute('aria-current', m[0]===state.metricKey?'true':'false');
        if(!avail){ b.style.opacity=0.45; b.style.cursor='not-allowed';
          b.title='免费数据源没有该口径的历史序列'; }
        else { b.title = (m[0]===i.metric)? '该指数主口径' : '查看真实序列（非推导）';
          b.onclick=function(){ state.metricKey=m[0]; renderAll(); }; }
        mg.appendChild(b);
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
      (data.direction==='inverse'?'（越高越便宜）':'（越高越贵）')+(data.is_alternate?'　·　真实序列':'');
    document.getElementById('leadPrice').textContent = '点位 '+grp(s.level)+'　'+
      (i.change_pct>0?'▲ +':(i.change_pct<0?'▼ ':'　'))+fmt(Math.abs(i.change_pct))+'%　'+i.data_date;
    var inv = data.direction==='inverse';
    var nearDanger = inv ? (s.current-t.danger) : (t.danger-s.current);
    var toChance = inv ? (t.opportunity-s.current) : (s.current-t.opportunity);
    var cls = s.zone==='低估'?'cold':(s.zone==='高估'?'hot':'');
    var line = data.metric_label+' 处在「<span class="'+cls+'">'+s.zone+'</span>」区间：当前值 '+
      fmt(s.current,data.digits)+'，十年分位点 <b>'+fmt(s.percentile)+'%</b>。';
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
    var approx = (i.flag==='derived' && !data.is_alternate);
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
    var html = '<caption>读数　'+data.metric_label+'　·　'+(state.win==='ALL'?'上市以来':state.win)+
      '　·　n = '+s.n+'</caption>';
    READ_ROWS.forEach(function(r){
      var key=r[0], label=r[1], gear='', flag='';
      if(key==='danger'||key==='median'||key==='opportunity'){
        gear=' <span class="gear" data-thr="'+key+'" title="自定义分位阈值">⚙</span>';
      }
      if(approx && (key==='danger'||key==='median'||key==='opportunity'||key==='percentile')){
        flag=' <span class="flag" title="推导值：实测阈值偏差 ≤5%、分位点约 ±6pp">≈</span>';
      }
      html += '<tr><td>'+label+gear+flag+'</td><td class="mono">'+vals[key]+'</td></tr>';
    });
    el.innerHTML = html;
    Array.prototype.forEach.call(el.querySelectorAll('[data-thr]'), function(node){
      node.onclick = function(){
        var which = node.getAttribute('data-thr');
        var cur = state.thr[thrKey()] || {danger:80, median:50, opportunity:20};
        var def = which==='median'?50:(which==='danger'?80:20);
        var label = {danger:'危险值', median:'中位数', opportunity:'机会值'}[which];
        var ans = window.prompt('把「'+label+'」改成第几分位？（0-100，留空恢复默认 '+def+
          '；股息率等反向指标会自动对调方向）', cur[which]||def);
        if(ans===null) return;
        ans = ans.trim();
        if(ans===''){ delete state.thr[thrKey()]; }
        else {
          var v = Number(ans);
          if(!isFinite(v) || v<0 || v>100){ window.alert('请输入 0-100 之间的数字'); return; }
          state.thr[thrKey()] = {danger:cur.danger||80, median:cur.median||50, opportunity:cur.opportunity||20};
          state.thr[thrKey()][which] = v;
        }
        renderAll();
      };
    });

    var notes = [];
    if(data.is_alternate){
      notes.push('<b>当前显示「'+data.metric_label+'」真实序列</b>（'+data.series.length+' 个周频点，第三方口径）：'+
        '分位点与三条判据都是真实数据，不带 ≈ 标记。该指数主口径是「'+i.metric_label+'」（推导口径），点上方的指标按钮可切回。');
    } else if(i.flag==='derived'){
      notes.push('<span class="flag">≈</span> <b>股息率历史为推导序列</b>（'+
        ((i.value_meta.method==='blend')?'全收益法 + PE锚定法几何平均':i.value_meta.method)+'，近端衰减校准 '+
        (((i.value_meta.calibration||{}).days)||'—')+' 天）：当前值 <b>'+fmt(s.current,data.digits)+
        '% 为官方真实值</b>，危险值 / 机会值 / 分位点为推导值，实测阈值偏差 ≤5%、分位点约 ±6pp。'+
        '官方真实值自 '+(i.value_meta.real_window_start||'—')+' 起逐日累积。');
    } else if(i.flag==='partial'){
      notes.push('<span class="flag">!</span> <b>真实市盈率仅自 '+(i.value_meta.daily_first_date||'—')+' 起</b>：'+
        '中证官方估值字段从这天开始提供（指数 '+(i.value_meta.index_launch_date||'')+
        ' 发布，行情按基日回溯，估值指标不回溯）；周频首个周点为 '+(i.value_meta.weekly_first_date||'')+
        '。更早区间不做推算，分位点只反映真实区间内的相对位置。');
    } else {
      notes.push('估值序列为第三方真实周频数据，统计口径与理杏仁「历史PE/PB」页一致。');
    }
    notes.push('统计口径：中位数 = 升序第 ⌊0.50n⌋ 项、危险值 = ⌊0.80n⌋、机会值 = ⌊0.20n⌋'+
      '（股息率 / 风险溢价为反向指标，方向对调）；分位点 = 小于当前值的样本占比；z 分数 = (当前值 − 平均值) / 样本标准差。');
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
    var dates = p.pts.map(function(x){return x.date;});
    var levels = p.pts.map(function(x){return x.level;});
    /* 横轴：显示 YY-MM 日期标签；窗口 >4 年按半年标，短窗口按季度标；
       一个月有 4~5 个周频点，只取该月第一个点，避免同名标签重复出现 */
    var spanYears = (Date.parse(dates[dates.length-1]) - Date.parse(dates[0])) / 3.15576e10;
    var monthSet = spanYears > 4 ? {'01':1,'07':1} : {'01':1,'04':1,'07':1,'10':1};
    function labelInterval(k, v){
      if(k<=0 || k>=dates.length-2) return false;
      if(!monthSet[v.slice(5,7)]) return false;
      return dates[k-1].slice(0,7) !== v.slice(0,7);
    }
    function fmtLabel(v){ return v.slice(2,4)+'-'+v.slice(5,7); }
    var mark = {silent:true, symbol:'none', label:{show:false}, data:[]};
    var add = function(y, color, dash){ if(y===null||y===undefined) return;
      mark.data.push({yAxis:y, lineStyle:{color:color,type:dash?'dashed':'solid',width:1.1}, label:{show:false}}); };
    if(p.view==='metric'){
      add(p.t.danger, C.red, true); add(p.t.median, C.dim, true); add(p.t.opportunity, C.olive, true);
      if(state.lines.mean) add(p.s.mean, C.faint, true);
      if(state.lines.std1){ add(p.s.std_plus, C.faint, true); add(p.s.std_minus, C.faint, true); }
    } else if(p.view==='percentile'){
      var over = state.thr[thrKey()] || {danger:80, median:50, opportunity:20};
      add(over.danger, C.red, true); add(over.median, C.dim, true); add(over.opportunity, C.olive, true);
    } else {
      add(2, C.faint, true); add(1, C.red, true); add(0, C.dim, true); add(-1, C.olive, true); add(-2, C.faint, true);
    }
    var band = (p.i.threshold_uncertainty && !p.data.is_alternate && p.view==='metric') ? p.i.threshold_uncertainty : null;
    var area = {silent:true, data:[]};
    if(band){
      area.data.push([{yAxis:p.t.danger*(1-band), itemStyle:{color:C.bandD}},{yAxis:p.t.danger*(1+band)}]);
      area.data.push([{yAxis:p.t.opportunity*(1-band), itemStyle:{color:C.bandC}},{yAxis:p.t.opportunity*(1+band)}]);
    }
    var nums = levels.filter(function(v){return v!==null && v!==undefined;});
    var ax = levelAxis(levels);
    /* 调仓标志：落在真实存在的周频点上，贴住图表底边（y = 点位轴最小值，符号上移半个高度） */
    var reb = [];
    (p.i.rebalance_dates||[]).forEach(function(d){
      if(d < dates[0]) { return; }
      for(var k=0;k<dates.length;k++){
        if(dates[k] >= d){ reb.push([dates[k], ax.min]); break; }
      }
    });
    return {
      animation:false,
      grid: small?{left:2,right:2,top:6,bottom:16}:{left:48,right:52,top:10,bottom:30},
      tooltip: small?{show:false}:{trigger:'axis',backgroundColor:'rgba(247,243,236,0.97)',borderColor:C.rule,
        textStyle:{color:C.ink,fontSize:12,fontFamily:'Menlo, monospace'},
        formatter:function(ps){ if(!ps.length) return ''; var k=ps[0].dataIndex, q=p.pts[k];
          var vw = p.data.views && p.data.views[state.win];
          var pct = vw && vw.pct ? vw.pct[k] : null;
          return q.date+'<br>'+p.data.metric_label+' '+fmt(q.value,p.data.digits)+
            (pct!==null&&pct!==undefined?'<br>分位点 '+fmt(pct)+'%':'')+
            (q.level?'<br>点位 '+grp(q.level):''); }},
      xAxis:{type:'category',data:dates,boundaryGap:false,
        axisLine:{lineStyle:{color: small?C.rule:C.dim}},
        axisTick: small?{show:false}:{show:true, length:3, lineStyle:{color:C.faint}, interval:labelInterval},
        axisLabel: small
          ? {show:true, interval:function(k){return k===0||k===dates.length-1;}, formatter:fmtLabel,
             color:C.faint, fontSize:9, fontFamily:'Menlo, monospace'}
          : {show:true, interval:labelInterval, formatter:fmtLabel, color:C.dim, fontSize:10.5,
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
        {type:'line',data:p.main,symbol:'none',z:2,connectNulls:true,lineStyle:{color:C.areaEdge,width:1},
         areaStyle:{color:C.area,origin:'start'},markLine:mark,markArea:area},
        {type:'line',data:levels,symbol:'none',yAxisIndex:1,z:3,lineStyle:{color:C.indigo,width:1}},
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
    items.push({t:'bar', c:C.indigo, label:'指数点位'});
    if(i.rebalance_dates && i.rebalance_dates.length){ items.push({t:'tri', label:'调仓标志'}); }
    if(state.view==='metric'){
      items.push({t:'dash', c:C.red, label:'危险值 '+fmt(t.danger,data.digits)});
      items.push({t:'dash', c:C.dim, label:'中位数 '+fmt(t.median,data.digits)});
      items.push({t:'dash', c:C.olive, label:'机会值 '+fmt(t.opportunity,data.digits)});
    } else if(state.view==='percentile'){
      var over = state.thr[thrKey()] || {danger:80, median:50, opportunity:20};
      items.push({t:'dash', c:C.red, label:'危险 '+over.danger+'%'});
      items.push({t:'dash', c:C.dim, label:'中位 '+over.median+'%'});
      items.push({t:'dash', c:C.olive, label:'机会 '+over.opportunity+'%'});
    } else {
      items.push({t:'dash', c:C.red, label:'+1σ'});
      items.push({t:'dash', c:C.dim, label:'0（均值）'});
      items.push({t:'dash', c:C.olive, label:'−1σ'});
    }
    var off = [{t:'dash', c:C.faint, label:'标准差(±1)', k:'std1'}, {t:'dash', c:C.faint, label:'平均值', k:'mean'}];
    function html(it, dim){
      var mark = it.t==='dot' ? '<span class="dot" style="background:'+it.c+'"></span>'
        : it.t==='bar' ? '<span class="bar" style="border-color:'+it.c+'"></span>'
        : it.t==='dash' ? '<span class="dash" style="border-color:'+it.c+'"></span>'
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
        '<td class="mono">'+(q.level?grp(q.level):'—')+'</td></tr>';
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
                  digits:i.digits, direction:i.direction};
      var sl = slice(data, win), s = i.stats[win];
      var card = document.createElement('div');
      card.className='card';
      card.setAttribute('aria-current', i.key===state.key?'true':'false');
      var unit = (i.metric==='pe'||i.metric==='pb')?' ×':' %';
      card.innerHTML = '<div class="n">'+i.name+'</div><div class="c mono">'+i.code+'　'+i.metric_label+
        '　'+(win==='ALL'?'上市以来':win)+'</div><div class="mini"></div>'+
        '<div class="r"><span>分位点 <b>'+fmt(s.percentile)+'%</b>　<b>'+s.zone+'</b></span>'+
        '<span><b>'+fmt(s.current,i.digits)+unit+'</b></span></div>';
      card.onclick = function(){
        state.key=i.key; state.metricKey=i.metric;
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
  function renderColophon(ctx){
    var i = ctx.i, s = ctx.s;
    var nameMap = {danjuan:'蛋卷（雪球系）', csindex:'中证指数官方', csindex_tr:'中证全收益指数', tencent:'腾讯行情'};
    var src = Object.keys(i.sources).filter(function(k){return i.sources[k];})
      .map(function(k){return nameMap[k]||k;}).join(' · ');
    var watchLine = '';
    if(D.rule_watch){
      var bad = (D.rule_watch.rows||[]).filter(function(r){return r.match===false;});
      watchLine = '口径核对：'+(D.rule_watch.article_date||'')+' 作者日更文章 · 命中 '+
        ((D.rule_watch.rows||[]).length)+' 个指数 · ';
      watchLine += bad.length
        ? '<b style="color:#8A1F12">❌ '+bad.length+' 处口径不一致：'+
          bad.map(function(r){return r.index_name+'（作者 '+r.author_metric+' / 本项目 '+r.our_metric+'）';}).join('、')+
          ' —— 请核对 compute/config.py</b>'
        : '✅ 口径与作者一致';
      watchLine += '。<br>';
    }
    document.getElementById('colophonLeft').innerHTML =
      watchLine+
      '数据来源：'+src+'　｜　数据截止 <em>'+i.data_date+'</em>　｜　窗口：'+
      (state.win==='ALL'?'上市以来':state.win)+'（周频，'+s.n+' 个点）　｜　口径与理杏仁「历史PE/PB」页一致。<br>'+
      '本页为个人研究复刻，不含任何商标或水印，<em>不构成投资建议</em>。';
    /* 区间行：真实数据起点（官方估值字段首日）与周频首点分别标明，避免把周频首点误当数据起点 */
    var rangeLine;
    if(i.flag==='partial' && i.value_meta.daily_first_date){
      rangeLine = '真实数据自 '+i.value_meta.daily_first_date+'（官方估值字段首日）起；周频首点 '+i.value_meta.weekly_first_date+
        ' → '+s.end;
    } else {
      rangeLine = '区间 '+s.start+' → '+s.end;
    }
    document.getElementById('colophonRight').innerHTML = rangeLine+'<br>生成 '+D.generated_at;
  }

  /* ------------------------------------------------ 总装 */
  function renderAll(){
    if(!state.key) state.key = D.indices[0].key;
    var i = idx();
    if(!state.win || !(i.stats[state.win])) state.win = i.recommended_window || D.default_window;
    if(!state.metricKey) state.metricKey = i.metric;
    else if(state.metricKey!==i.metric && !i.alternates[state.metricKey]) state.metricKey = i.metric;

    var alertEl = document.getElementById('alert');
    var badRows = D.rule_watch ? (D.rule_watch.rows||[]).filter(function(r){return r.match===false;}) : [];
    alertEl.innerHTML = badRows.length
      ? '<div class="alarm">⚠ 口径变化提醒（'+(D.rule_watch.article_date||'')+' 作者日更文章）：'+
        badRows.map(function(r){return r.index_name+' 用「'+r.author_metric+'」，本项目配置的是「'+r.our_metric+'」';}).join('；')+
        '。请在 compute/config.py 里核对后更新口径。</div>'
      : '';
    document.getElementById('mastMeta').innerHTML =
      '数据截止 <b>'+i.data_date+'</b><br>周频 · '+D.indices.length+' 个指数 · 生成 <b>'+D.generated_at+'</b>';
    var rail = document.getElementById('rail'); rail.innerHTML='';
    D.indices.forEach(function(x){
      var b=document.createElement('button');
      b.setAttribute('aria-current', x.key===state.key?'true':'false');
      b.innerHTML = x.name+'<span class="code mono">'+x.code+'</span>';
      b.onclick = function(){
        state.key=x.key; state.metricKey=x.metric;
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
    var lines = ['date,'+data.metric_label+',percentile,level'];
    sl.points.forEach(function(p,k){
      var pct = sl.views.pct? sl.views.pct[k] : '';
      lines.push([p.date, p.value, (pct===''||pct===null||pct===undefined)?'':pct, p.level].join(','));
    });
    var blob = new Blob(['\ufeff'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = i.name+'_'+data.metric_label+'_'+state.win+'.csv';
    a.click();
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
    state.metricKey = q.metric || target.metric;
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
