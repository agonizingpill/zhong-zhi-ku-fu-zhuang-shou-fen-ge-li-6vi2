"""退种活力拟合：同作物历次退种（离库天数, 实测发芽率）一元线性回归。

只用同作物、已验收、带离库日期和实测发芽率的历史退种作样本；
样本不足 RETURN_MIN_SAMPLES 时不预测，业务侧隔离补测。
口径固定：OLS、均值点估计、训练内残差标准误、决定系数，全部裁到 0–100。
"""
import numpy as np
from .constants import RETURN_MIN_SAMPLES,RETURN_PASS_RATE

def fit(crop,rows,leave_days):
    """rows: [(leave_days, measured_pct),...] 已按同作物过滤。"""
    points=sorted((float(a),float(b)) for a,b in rows if a is not None and b is not None)
    n=len(points)
    if n<RETURN_MIN_SAMPLES:
        return {'model':'OLS(leave_days -> measured_pct)','crop':crop,'sample_rows':n,'min_samples':RETURN_MIN_SAMPLES,'predicted_pct':None,'residual_std_pct':None,'r2':None,'pass_threshold_pct':RETURN_PASS_RATE,'decision':'insufficient_sample','decision_reason':f'同作物历史退种样本{n}条，少于{RETURN_MIN_SAMPLES}条，隔离补测','training_points':points}
    x=np.array([p[0] for p in points]);y=np.array([p[1] for p in points])
    xm,ym=x.mean(),y.mean();sxx=float(((x-xm)**2).sum());sxy=float(((x-xm)*(y-ym)).sum())
    slope=sxy/sxx;intercept=float(ym-slope*xm)
    pred=intercept+slope*float(leave_days)
    resid=y-(intercept+slope*x)
    r2=1-float((resid**2).sum())/float(((y-ym)**2).sum()) if float(((y-ym)**2).sum()) else None
    rstd=float(np.sqrt((resid**2).sum()/max(n-2,1)))
    value=max(0.0,min(100.0,pred))
    decision='pass' if value>=RETURN_PASS_RATE else 'isolate_low_vitality'
    return {'model':'OLS(leave_days -> measured_pct)','crop':crop,'sample_rows':n,'min_samples':RETURN_MIN_SAMPLES,'intercept':round(intercept,4),'slope':round(slope,6),'predicted_pct':round(value,3),'residual_std_pct':round(rstd,3),'r2':None if r2 is None else round(r2,4),'pass_threshold_pct':RETURN_PASS_RATE,'decision':decision,'decision_reason':('预测发芽率≥80%，可待验收' if decision=='pass' else '预测发芽率低于80%，隔离到补测合格'),'input_leave_days':leave_days,'training_points':points}
