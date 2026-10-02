"""Fixed axis calibration; no amplitude rescaling or date-shift fitting."""
import json
import numpy as np
import pandas as pd
from PIL import Image
from src.data.common import ROOT

POINTS=[
 ('2014-07','indicator_peak','作者标注顶；恒指2015-04，领先9月','high'),
 ('2015-04','hsi_peak','与指标2014-07对应','high'),
 ('2015-07','indicator_trough','作者标注底；恒指2016-02，领先7月','high'),
 ('2016-02','hsi_trough','与指标2015-07对应','high'),
 ('2017-10','indicator_peak','作者标注顶；恒指2018-01，领先3月','high'),
 ('2018-01','hsi_peak','与指标2017-10对应','high'),
 ('2018-10','indicator_trough','恒指无对应，信号弱','high'),
 ('2019-06','indicator_peak','恒指无对应，信号弱','high'),
 ('2020-03','indicator_trough','与恒指2020-03同步','high'),
 ('2020-03','hsi_trough','与指标2020-03同步','high'),
 ('2021-03','indicator_peak','恒指2021-02，滞后1月','high'),
 ('2021-02','hsi_peak','与指标2021-03对应','high'),
 ('2021-08','indicator_trough','框内月份可辨，恒指无对应','medium'),
 ('2022-11','indicator_trough','恒指2022-10，滞后1月','high'),
 ('2022-10','hsi_trough','与指标2022-11对应','high'),
 ('2023-04','indicator_peak','恒指无对应，信号弱','high'),
 ('2024-01','hsi_trough','指标无对应','high'),
 ('2025-06','indicator_peak','恒指2025-10，领先4月','high'),
 ('2025-10','hsi_peak','作者标注，独立于当前市场数据','medium')]

def extract():
 refs=pd.DataFrame(POINTS,columns=['reference_date','type','description','confidence']);refs['source']='docs/indicator_original.PNG; manual visual transcription'
 refs.to_csv(ROOT/'output/reference_turning_points.csv',index=False)
 a=np.asarray(Image.open(ROOT/'docs/indicator_original.PNG').convert('RGB')).astype(int)
 # Original 1320x2868 screenshot, approximate chart calibration by tick marks.
 x0,x1=103,1194;y0,y1=1650,2075
 b=a[y0:y1,x0:x1];r,g,blue=b[:,:,0],b[:,:,1],b[:,:,2]
 mask=(r<110)&(blue<180)&(blue-r>25)&(g-r>10)&(blue-g>8)
 path=[]
 for j in range(mask.shape[1]):
  ys=np.flatnonzero(mask[:,j])+y0
  # Multiple separated blue objects make this column ambiguous: retain NaN.
  if len(ys) and ys.max()-ys.min()<=14:path.append((j+x0,float(np.median(ys))))
 pixels=pd.DataFrame(path,columns=['pixel_x','pixel_y']);pixels.to_csv(ROOT/'data/interim/screenshot_blue_pixels.csv',index=False)
 d0=pd.Timestamp('2014-01-01');d1=pd.Timestamp('2026-01-01');pixels_per_day=(1139.-213.)/(d1-d0).days
 rows=[]
 for m in pd.period_range('2012-07','2026-08',freq='M'):
  x=213.+(m.end_time.normalize()-d0).days*pixels_per_day
  p=pixels[(pixels.pixel_x-x).abs()<=2.5]
  value=(1842.-p.pixel_y.median())/96.5 if len(p)>=2 else np.nan
  rows.append((str(m),value,len(p),'medium' if len(p)>=4 else 'low'))
 curve=pd.DataFrame(rows,columns=['date','reference_indicator','pixel_columns','confidence'])
 curve.to_csv(ROOT/'output/tables/screenshot_curve.csv',index=False)
 metadata=dict(image_size=[1320,2868],x_tick_2014_01_01=213,x_tick_2026_01_01=1139,y_zero=1842,pixels_per_z=96.5,date_rule='month end',precision='approximate; axis and compression uncertainty; no fitting to candidate data',shape_score='1/(1+direct absolute-level RMSE); no scaling or lag search')
 (ROOT/'output/diagnostics/screenshot_calibration.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 return refs,curve
