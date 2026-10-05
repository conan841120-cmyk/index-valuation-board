import React from 'react';
import {createRoot} from 'react-dom/client';
import {DashboardContent} from './DashboardContent.jsx';
import {DataProvider} from './ui.jsx';
async function init(){
 const response=await fetch('snapshot.json',{cache:'no-cache'});
 if(!response.ok)throw new Error('snapshot unavailable');
 const snapshot=await response.json();
 if(snapshot.schema_version!==1||snapshot.symbol!=='^GSPC')throw new Error('snapshot identity');
 const checked=new Date(snapshot.refresh.checked_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
 document.getElementById('status').textContent='收盘截至 '+snapshot.research.data_end+' · '+(snapshot.refresh.state==='ok'?'刷新成功':snapshot.refresh.state==='failed'?'刷新失败，保留上一版数据':'等待首次云端刷新')+' · 最近检查 '+checked+'（北京时间）';
 createRoot(document.getElementById('sp500-app')).render(<DataProvider snapshot={snapshot}><DashboardContent/></DataProvider>);
}
init().catch(()=>{document.getElementById('status').textContent='数据读取失败，请刷新页面；仍失败时暂不使用概率。';});
