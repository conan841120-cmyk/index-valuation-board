"""Figures retain missing values; historical comparison marks gap connections."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from src.data.common import ROOT
from src.indicators.leading_indicator import FACTORS

COLORS=['#2478a4','#cd7545','#449877','#9366ad']
LABELS=['Retail YoY','PPI YoY','HK M2 total YoY','Credit impulse']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120,'savefig.dpi':180})

def finish(fig,name):
 fig.savefig(ROOT/'output/charts'/name,bbox_inches='tight',facecolor='white');plt.close(fig)

def calendar(ax):
 ax.xaxis.set_major_locator(mdates.YearLocator(2));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
 ax.grid(axis='y',color='#dedede',linewidth=.6);ax.set_axisbelow(True)

def four_panels(f,columns,title,name,units):
 fig,axes=plt.subplots(4,1,figsize=(13,9),sharex=True)
 dates=f.index.to_timestamp('M')
 for ax,col,label,color,unit in zip(axes,columns,LABELS,COLORS,units):
  ax.plot(dates,f[col],color=color,lw=1.5);ax.axhline(0,color='#888888',lw=.5)
  ax.set_ylabel(unit);ax.set_title(label,loc='left',fontsize=11);calendar(ax)
 fig.suptitle(title,fontsize=16,x=.07,ha='left');fig.tight_layout(rect=(0,0,1,.95));finish(fig,name)

def historical_comparison(f,config):
 with plt.rc_context({'font.family':'Heiti SC','axes.unicode_minus':False}):
  f=f.loc[config['composite_start']:];dates=f.index.to_timestamp('M')
  fig,left=plt.subplots(figsize=(14,6));right=left.twinx();right.spines['right'].set_visible(True)
  indicator,=left.plot(dates,f.leading_indicator,color='#243e50',lw=1.8,label='领先指标（左轴）')
  known=f.leading_indicator.dropna();gap_line=None
  for i in range(1,len(known)):
   if known.index[i].ordinal-known.index[i-1].ordinal>1:
    gap_line,=left.plot(known.index[i-1:i+1].to_timestamp('M'),known.iloc[i-1:i+1],color='#243e50',lw=1.8,ls='--',label='缺失月连线，无月度值')
  hsi,=right.plot(dates,f.hsi_close,color='#bd864d',lw=1.4,label='恒生指数（右轴）',alpha=.9)
  left.set_ylim(-2.5,2);right.set_ylim(12000,36000);left.set_ylabel('领先指标（加权标准分）');right.set_ylabel('恒生指数（点）')
  left.set_title('恒生指数领先指标（实时标准化版）｜历史复现',loc='left',fontsize=17,pad=34)
  variance={'explicit_population':'显式总体方差','explicit_unbiased':'显式无偏加权方差','pandas_adjust_true':'递推加权方差（历史权重校正）','pandas_adjust_false':'递推加权方差（历史权重不校正）'}[config['standardization_mode']]
  gdp={'observation_period':'按观察期映射','release_aware':'按已核验发布日期映射'}[config['gdp_alignment_mode']]
  left.text(0,1.045,'社零同比／出厂价格同比／香港广义货币总额同比／信用脉冲；四项等权；半衰期36个月；'+variance+'；国内生产总值'+gdp,transform=left.transAxes,fontsize=9,color='#555')
  calendar(left);left.axhline(0,color='#888',lw=.6)
  for month,offset in [('2014-07',.35),('2015-07',-.4),('2017-10',.35),('2020-03',-.3),('2021-03',.5),('2022-11',.4),('2025-06',.45)]:
   p=pd.Period(month,'M');v=f.loc[p,'leading_indicator']
   if pd.notna(v):left.annotate(month,(p.to_timestamp('M'),v),xytext=(p.to_timestamp('M'),v+offset),ha='center',fontsize=8,arrowprops={'arrowstyle':'-','color':'#777','lw':.6})
  lines=[indicator,hsi]+([gap_line] if gap_line is not None else [])
  left.legend(lines,[x.get_label() for x in lines],loc='upper left',frameon=False,ncol=3,fontsize=9)
  fig.text(.07,.025,'虚线仅连接历史有效端点，缺失月份的指标仍为空值；不能作为实时月度信号。标注日期沿用原截图。',fontsize=9,color='#666')
  fig.text(.07,-.01,'历史数据含最新修订；本图不代表已还原当时的数据版本。',fontsize=9,color='#666')
  finish(fig,'indicator_vs_hsi.png')

def generate(f,data,frames,comparison,curve,strict,config):
 f=f.loc[config['composite_start']:].copy();dates=f.index.to_timestamp('M')
 raw=f.copy();raw['credit_impulse_pct']=100*raw.credit_impulse_3m
 four_panels(raw,['retail_yoy','ppi_yoy','hk_m2_yoy','credit_impulse_pct'],'Four original macro factors | official data','raw_components.png',['%','%','%','% of 2Q nominal GDP'])
 four_panels(f,['z_'+n for n in FACTORS],'Real-time weighted Z-scores | half-life 36 months','zscore_components.png',['Z-score']*4)
 fig,ax=plt.subplots(figsize=(13,4.5));ax.plot(dates,f.leading_indicator,color='#243e50',lw=1.7)
 ax.set_title('Hang Seng leading indicator | four equal components',loc='left',fontsize=15)
 ax.set_ylabel('Weighted Z-score');ax.axhline(0,color='#888',lw=.7);calendar(ax)
 fig.text(.07,.015,'Jan/Feb gaps are retained. History is latest-vintage; variance implementation is provisional.',fontsize=9,color='#666')
 finish(fig,'leading_indicator.png')
 h=data['hsi'].copy();h.index=pd.PeriodIndex(h.observation_period,freq='M');h=h.loc[str(f.index[0]):str(f.index[-1])]
 fig,ax=plt.subplots(figsize=(13,4.5));ax.plot(h.index.to_timestamp('M'),h.value,color='#bd864d',lw=1.6)
 ax.set_title('Hang Seng Index | last trading-day monthly close',loc='left',fontsize=15);ax.set_ylabel('Index points');calendar(ax);finish(fig,'hsi.png')
 historical_comparison(f,config)
 fig,ax=plt.subplots(figsize=(14,5.5));positive=np.zeros(len(f));negative=np.zeros(len(f))
 for name,label,color in zip(FACTORS,LABELS,COLORS):
  v=f['contribution_'+name].to_numpy();bottom=np.where(v>=0,positive,negative)
  ax.bar(dates,v,bottom=bottom,width=25,color=color,label='.25 × '+label,alpha=.85)
  positive+=np.where(np.isfinite(v)&(v>=0),v,0);negative+=np.where(np.isfinite(v)&(v<0),v,0)
 ax.plot(dates,f.leading_indicator,color='#243e50',lw=1.5,label='Composite')
 ax.set_ylabel('Contribution (Z-score)');ax.set_title('Component contributions | fixed weights 0.25',loc='left',fontsize=16)
 ax.axhline(0,color='#777',lw=.7);calendar(ax);ax.legend(loc='upper left',ncol=3,frameon=False,fontsize=9)
 fig.text(.07,.01,'Components are shown independently; the composite stays NaN if any component is missing.',fontsize=9,color='#666')
 finish(fig,'component_contributions.png')
 fig,ax=plt.subplots(figsize=(13,4.5));ax.plot(dates,raw.credit_impulse_pct,color=COLORS[3],label='Trailing 3-month mean')
 ax.plot(dates,100*f.credit_impulse_raw,color=COLORS[3],alpha=.3,label='Raw ratio × 100')
 ax.set_ylabel('% of 2Q nominal GDP');ax.set_title('Credit impulse | (SF6[t] − SF6[t−12]) / GDP2Q[t]',loc='left',fontsize=15)
 ax.axhline(0,color='#888',lw=.7);calendar(ax);ax.legend(frameon=False);finish(fig,'credit_impulse.png')
 fig,axes=plt.subplots(2,1,figsize=(14,9),sharex=True)
 for ax,gdp in zip(axes,['observation_period','release_aware']):
  for row in comparison[comparison.gdp_alignment_mode.eq(gdp)].itertuples():
   s=frames[row.candidate_id].leading_indicator.loc[config['composite_start']:]
   ax.plot(s.index.to_timestamp('M'),s,label=row.candidate_id+': '+row.standardization_mode,lw=1.2,alpha=.85)
  ax.scatter(pd.PeriodIndex(curve.date,freq='M').to_timestamp('M'),curve.reference_indicator,s=7,color='#333',alpha=.6,label='Screenshot extraction (approx.)')
  ax.set_title(gdp+(' | early publication dates unavailable; partial history' if gdp=='release_aware' else ' | fixed absolute screenshot levels'),loc='left')
  ax.set_ylabel('Indicator');calendar(ax);ax.legend(frameon=False,ncol=2,fontsize=9)
 fig.tight_layout();finish(fig,'candidate_vs_screenshot.png')
 valid=strict[strict.leading_indicator.notna()]
 fig,ax=plt.subplots(figsize=(13,4.5))
 if len(valid):ax.plot(pd.to_datetime(valid.as_of_date),valid.leading_indicator,color='#446d80',lw=1.5)
 ax.set_title('Release-gated availability | incomplete vintages and early dates',loc='left',fontsize=15)
 ax.set_ylabel('Latest available indicator');calendar(ax)
 fig.text(.07,.01,'As-of date is different from observation month. This is NOT certified historical-vintage point-in-time data.',fontsize=9,color='#a04b28')
 finish(fig,'strict_real_time.png')
