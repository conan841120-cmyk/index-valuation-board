"""Offline reproduction by default; explicit flags acquire or refresh sources."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from src.data.common import ROOT,RAW
from src.indicators.leading_indicator import build,load_config,FACTORS
from src.validation.screenshot_reference import extract
from src.validation.candidate_comparison import compare
from src.validation.point_in_time import real_time_history
from src.visualization.plot_indicator import generate

DATASETS=('retail','ppi','hk_m2','social_financing','gdp','hsi')

def load_data():
 return {name:pd.read_csv(ROOT/'data/processed'/f'{name}.csv') for name in DATASETS}

def acquire(refresh):
 from src.data import download_nbs,download_pboc,download_hkma,download_hsi,download_release_dates
 for name in ('retail','ppi','gdp'):download_nbs.download(name,refresh)
 download_pboc.download(refresh);download_hkma.download(refresh);download_hsi.download(refresh)
 download_release_dates.nbs(refresh);download_release_dates.pboc(refresh)

def quality(data):
 rows=[];missing=[]
 for name,d in data.items():
  valid=d[d.value.notna()]
  if d.observation_period.duplicated().any():raise ValueError(f'{name}: duplicate periods')
  row=dict(dataset=name,rows=len(d),valid_rows=len(valid),first_valid=valid.observation_period.min(),last_valid=valid.observation_period.max(),unit=';'.join(d.unit.unique()),missing_values=int(d.value.isna().sum()),duplicate_periods=0,verified_release_dates=int(valid.release_date.notna().sum()))
  rows.append(row);print('DATA QUALITY',json.dumps(row),flush=True)
  for p in d.loc[d.value.isna(),'observation_period']:missing.append(dict(dataset=name,observation_period=p,reason='Official field blank; retained NaN'))
 pd.DataFrame(rows).to_csv(ROOT/'output/diagnostics/data_quality.csv',index=False)
 pd.DataFrame(missing).to_csv(ROOT/'output/diagnostics/missing_values.csv',index=False)
 manifest=[]
 for p in sorted(RAW.glob('*.meta.json')):
  record=json.loads(p.read_text());record['cache_metadata_file']=str(p.relative_to(ROOT));manifest.append(record)
 (ROOT/'output/diagnostics/raw_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 return pd.DataFrame(rows)

def latest_snapshot(f,comparison,best,config,strict):
 valid=f.leading_indicator.dropna();month=valid.index[-1];row=f.loc[month];previous=f.loc[month-1]
 lines=['# 最新有效月份解释','',f'计算时间：{pd.Timestamp.now().isoformat(timespec="seconds")}（本机时间）',f'观察月份：**{month}**；GDP={config["gdp_alignment_mode"]}；standardization={config["standardization_mode"]}。','',f'最终指标：**{row.leading_indicator:.6f}**；上月（{month-1}）：{previous.leading_indicator:.6f}；变化：**{row.leading_indicator-previous.leading_indicator:+.6f}**。','', '| 组件 | 原始值 | Z-score | 0.25 × Z | 相比上月的贡献变化 |','|---|---:|---:|---:|---:|']
 for name in FACTORS:
  raw=row.credit_impulse_3m if name=='credit_impulse' else row[name+'_yoy']
  label=f'{raw:.8f}（比例；{100*raw:.4f}%）' if name=='credit_impulse' else f'{raw:.4f}%'
  change=row['contribution_'+name]-previous['contribution_'+name]
  lines.append(f'| {name} | {label} | {row["z_"+name]:.6f} | {row["contribution_"+name]:.6f} | {change:+.6f} |')
 lines+=['', '贡献变化之和等于指标变化；正数推高指标，负数压低指标。','', '本结果用于算法复现，不含投资建议。缺少任一组件的月份保持 NaN，未把其余组件改为 1/3。', '',f'截图比较的数值最优候选：{best}；这不等于确认原作者算法。无偏显式方差与 pandas adjust=True 等价，population 的误差差距小于截图精度。','', '## 发布日期门控结果','']
 sv=strict[strict.leading_indicator.notna()]
 if len(sv):
  last=sv.iloc[-1];lines.append(f'截至 {last.as_of_date}，最新可形成的观察月份 {last.observation_period_used}，指标 {last.leading_indicator:.6f}，距离当前观察月 {int(last.stale_months)} 个月。')
 lines+=['','该门控版本仅使用已核验发布日期，但早期发布日期不全，且 NBS/社融历史值包含修订。**不能认证为真实历史 vintage 的严格实时回测**；它与历史复现的初始化样本不同，数值不得混用。']
 (ROOT/'output/latest_snapshot.md').write_text('\n'.join(lines)+'\n')
 return row

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true',help='Acquire missing sources or reparse cached sources');parser.add_argument('--refresh',action='store_true',help='Explicitly download current source responses again')
 args=parser.parse_args()
 for directory in ('data/raw','data/interim','data/processed','output/charts','output/tables','output/diagnostics','output/candidates'):(ROOT/directory).mkdir(parents=True,exist_ok=True)
 if args.download or args.refresh:acquire(args.refresh)
 data=load_data();config=load_config();quality(data)
 refs,curve=extract();comparison,frames,best=compare(data,refs,curve,config)
 selected=comparison[(comparison.gdp_alignment_mode==config['gdp_alignment_mode'])&(comparison.standardization_mode==config['standardization_mode'])].iloc[0]
 f=frames[selected.candidate_id]
 if config['gdp_alignment_mode']=='observation_period' and str(f.leading_indicator.first_valid_index())!='2012-07':raise ValueError('Historical composite must begin 2012-07')
 f.to_csv(ROOT/'output/diagnostics/indicator_diagnostics.csv')
 f.loc[config['composite_start']:].to_csv(ROOT/'data/processed/historical_replication.csv')
 f.loc[config['composite_start']:].to_csv(ROOT/'data/processed/leading_indicator.csv')
 ci_cols=['social_financing_monthly','sf6','sf6_last_year','sf6_difference','gdp_current_quarter','gdp_previous_quarter','gdp_2q','credit_impulse_raw','credit_impulse_3m']
 f[ci_cols].to_csv(ROOT/'output/diagnostics/credit_impulse_diagnostics.csv')
 print('Building release-gated as-of snapshots (early dates and vintages remain incomplete)',flush=True)
 strict=real_time_history(data,config['standardization_mode'],config)
 strict.to_csv(ROOT/'output/diagnostics/strict_real_time_diagnostics.csv',index=False)
 strict.to_csv(ROOT/'data/processed/strict_real_time.csv',index=False)
 strict.to_csv(ROOT/'output/tables/strict_real_time.csv',index=False)
 valid=strict[strict.leading_indicator.notna()]
 if len(valid) and (pd.to_datetime(valid.max_known_input_release_date)>pd.to_datetime(valid.as_of_date)).any():raise ValueError('Unreleased input entered a snapshot')
 generate(f,data,frames,comparison,curve,strict,config);row=latest_snapshot(f,comparison,best,config,strict)
 provenance={'computed_at':pd.Timestamp.now().isoformat(),'config':config,'selected_candidate':selected.candidate_id,'numerically_closest_screenshot_candidate':best,'first_valid':str(f.leading_indicator.first_valid_index()),'last_valid':str(f.leading_indicator.last_valid_index()),'nonmissing_observations':int(f.leading_indicator.notna().sum()),'historical_vintage_certified':False,'source_code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').rglob('*.py'))}}
 (ROOT/'output/diagnostics/run_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
 print('COMPLETE',json.dumps({k:provenance[k] for k in ('selected_candidate','first_valid','last_valid','nonmissing_observations')}),'latest indicator',row.leading_indicator,flush=True)

if __name__=='__main__':main()
