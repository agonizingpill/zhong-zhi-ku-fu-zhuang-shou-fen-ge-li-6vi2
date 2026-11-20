from datetime import date
from fastapi import HTTPException
from sqlalchemy import select,func
from .models import Accession,Lot,Distribution,ReturnOrder,ReturnBag
from .common import lock,pack,audit
from .constants import RETURN_PASS_RATE
from .return_vitality import fit

def _measured_pct(s,ro):
    """退种单实测发芽率：优先补测；否则汇总登记袋的实测。"""
    if ro.retest_sampled:
        return round(100*ro.retest_germinated/ro.retest_sampled,3)
    bags=s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id,ReturnBag.sampled.is_not(None))).all()
    ts=sum(b.sampled or 0 for b in bags);tg=sum(b.germinated or 0 for b in bags)
    return round(100*tg/ts,3) if ts else None

def _history_rows(s,crop):
    """同作物、已验收、有离库天数与实测发芽率的历次退种样本。"""
    rows=[]
    orders=s.scalars(select(ReturnOrder).where(ReturnOrder.state=='accepted',ReturnOrder.leave_days.is_not(None))).all()
    for ro in orders:
        d=s.get(Distribution,ro.distribution_id);lot=s.get(Lot,d.lot_id);a=s.get(Accession,lot.accession_id)
        if a.crop!=crop:continue
        pct=_measured_pct(s,ro)
        if pct is not None:rows.append((ro.leave_days,pct))
    return rows

def register(s,d,u):
    # 父行锁：以已签收共享单串行化同单并发的退回与撤回，保证待验+已收不超原签发量。
    dist=lock(s,Distribution,d.distribution_id)
    if dist.state!='received':raise HTTPException(409,'只能按已签收共享单登记退种')
    lot=s.get(Lot,dist.lot_id);accession=s.get(Accession,lot.accession_id)
    new_seeds=sum(b.seeds for b in d.bags)
    bound=int(s.scalar(select(func.coalesce(func.sum(ReturnBag.seeds),0)).select_from(ReturnBag).join(ReturnOrder,ReturnBag.return_order_id==ReturnOrder.id).where(ReturnOrder.distribution_id==dist.id,ReturnBag.state.in_(('pending','isolated','accepted')))) or 0)
    if bound+new_seeds>dist.seeds:raise HTTPException(409,f'待验与已收粒数合计不能超过原签发量{dist.seeds}粒（已占{bound}粒，本次{new_seeds}粒）')
    today=d.return_date or date.today()
    leave_days=None
    if dist.leave_date:
        leave_days=(today-date.fromisoformat(dist.leave_date)).days
        if leave_days<0:raise HTTPException(409,'退回日期不能早于共享单离库日期')
    ro=ReturnOrder(code=d.code,distribution_id=dist.id,state='pending',leave_days=leave_days)
    s.add(ro);s.flush()
    for b in d.bags:s.add(ReturnBag(return_order_id=ro.id,bag_no=b.bag_no,seeds=b.seeds,sampled=b.sampled,germinated=b.germinated,state='pending'))
    s.flush()
    reasons=[]
    if leave_days is None:
        result={'decision':'missing_leave_date','decision_reason':'旧共享单缺离库日期，无法计算离库天数，隔离补测','crop':accession.crop,'sample_rows':len(_history_rows(s,accession.crop)),'pass_threshold_pct':RETURN_PASS_RATE}
        reasons.append(result['decision_reason'])
    else:
        result=fit(accession.crop,_history_rows(s,accession.crop),leave_days)
        if result['decision']!='pass':reasons.append(result['decision_reason'])
    own=_measured_pct(s,ro)
    if own is not None and own<RETURN_PASS_RATE:
        result['decision']='isolate_low_observed';result['decision_reason']=(result.get('decision_reason','')+f'；本单实测发芽率{own}%低于80%，隔离补测').strip('；');reasons.append('本单实测发芽率低于80%')
    isolated=bool(reasons)
    ro.state='isolated' if isolated else 'pending';ro.prediction=result
    for b in s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id)).all():b.state=ro.state
    audit(s,u,('登记退种并隔离补测 ' if isolated else '登记退种 ')+d.code)
    return pack(ro)|{'bags':[pack(b) for b in s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id)).all()]}

def withdraw_bag(s,bag_id,u):
    pre=s.get(ReturnBag,bag_id)
    if not pre:raise HTTPException(404,'退种袋不存在')
    ro_pre=s.get(ReturnOrder,pre.return_order_id)
    # 先锁共享单父行，与register保持同一锁序。
    lock(s,Distribution,ro_pre.distribution_id)
    ro=lock(s,ReturnOrder,ro_pre.id);b=lock(s,ReturnBag,bag_id)
    if b.state not in ('pending','isolated'):raise HTTPException(409,'该袋已验收或已撤回，不能重复撤回')
    b.state='withdrawn'
    audit(s,u,f'撤回待验退种袋 {b.bag_no}（{b.seeds}粒），额度退还 {ro.code}')
    active=s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id,ReturnBag.state.in_(('pending','isolated')))).all()
    if not active:ro.state='withdrawn'
    return pack(b)

def retest(s,id,d,u):
    pre=s.get(ReturnOrder,id)
    if not pre:raise HTTPException(404,'退种单不存在')
    dist=lock(s,Distribution,pre.distribution_id);ro=lock(s,ReturnOrder,id)
    if ro.state not in ('isolated',):raise HTTPException(409,'仅隔离退种单需要补测')
    ro.retest_sampled=d.sampled;ro.retest_germinated=d.germinated
    pct=round(100*d.germinated/d.sampled,3)
    if pct<RETURN_PASS_RATE:
        audit(s,u,f'退种补测不合格 {pct}%，继续隔离 {ro.code}')
    else:
        ro.state='pending'
        for b in s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id,ReturnBag.state=='isolated')).all():b.state='pending'
        audit(s,u,f'退种补测合格 {pct}%，解除隔离 {ro.code}')
    return pack(ro)

def accept(s,id,u,body=None):
    pre=s.get(ReturnOrder,id)
    if not pre:raise HTTPException(404,'退种单不存在')
    dist_pre=s.get(Distribution,pre.distribution_id);lot_pre=s.get(Lot,dist_pre.lot_id)
    # 与回库一致：先锁父种质做保底聚合，再锁退种根记录；验收不重复入库。
    lock(s,Accession,lot_pre.accession_id)
    lock(s,Distribution,pre.distribution_id)
    ro=lock(s,ReturnOrder,id)
    if ro.state=='accepted':raise HTTPException(409,'该退种单已验收入库，不可重复验收')
    if ro.state!='pending':raise HTTPException(409,'隔离或已撤回退种单不能验收，先补测合格')
    bags=s.scalars(select(ReturnBag).where(ReturnBag.return_order_id==ro.id,ReturnBag.state=='pending')).all()
    if not bags:raise HTTPException(409,'没有可验收的待验袋')
    check_pct=None
    if body and body.sampled:
        check_pct=round(100*body.germinated/body.sampled,3)
        if check_pct<RETURN_PASS_RATE:
            ro.retest_sampled=body.sampled;ro.retest_germinated=body.germinated;ro.state='isolated'
            for b in bags:b.state='isolated'
            audit(s,u,f'验收实测发芽率{check_pct}%低于80%，转隔离补测 {ro.code}')
            s.commit()  # 隔离状态须随失败验收落库；路由侧因异常不再提交
            raise HTTPException(409,f'验收实测发芽率{check_pct}%低于80%，转隔离补测')
    seeds=sum(b.seeds for b in bags)
    measured=_measured_pct(s,ro)
    child=Lot(accession_id=lot_pre.accession_id,code=ro.code+'-G'+str(lot_pre.generation),generation=lot_pre.generation,available=seeds,stored_months=round(lot_pre.stored_months+(ro.leave_days or 0)/30.0,3),temperature=lot_pre.temperature,initial_rate=measured if measured is not None else lot_pre.initial_rate,parent_lot_id=lot_pre.id)
    s.add(child);s.flush()
    for b in bags:b.state='accepted'
    ro.state='accepted';ro.accepted_lot_id=child.id
    ro.basis={'distribution':pack(dist_pre),'origin_lot':pack(lot_pre),'accepted_lot':pack(child),'leave_days':ro.leave_days,'prediction':ro.prediction,'retest':{'sampled':ro.retest_sampled,'germinated':ro.retest_germinated,'pct':measured},'acceptance_check':None if check_pct is None else {'sampled':body.sampled,'germinated':body.germinated,'pct':check_pct},'bags':[pack(b) for b in bags],'seeds':seeds,'note':'验收前待验退种不计保底；验收后另立同代种批，凭原共享单可查验收依据'}
    audit(s,u,f'主管验收退种入库 {ro.code}，新批 {child.code} {seeds}粒')
    return pack(ro)
