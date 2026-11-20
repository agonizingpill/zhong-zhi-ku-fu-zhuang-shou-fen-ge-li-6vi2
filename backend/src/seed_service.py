from sqlalchemy import select,func
from .db import Base,engine,Session
from .models import *
from .auth import hashed

def seed():
    Base.metadata.create_all(engine)
    with Session() as s:
        for role in ('operator','supervisor','viewer'):
            email=role+'@qinghe.demo'
            if not s.scalar(select(User).where(User.email==email)):s.add(User(email=email,role=role,password_hash=hashed('Seeds2026!')))
        a=s.scalar(select(Accession).where(Accession.code=='QH-021'))
        if not a:a=Accession(code='QH-021',crop='青豆',name='青禾早熟青豆',origin='青禾北圃2023采集',minimum=300);s.add(a);s.flush()
        for code,generation,available in [('QH-021-G3',3,960),('QH-021-POLLEN',3,400)]:
            if not s.scalar(select(Lot).where(Lot.code==code)):s.add(Lot(accession_id=a.id,code=code,generation=generation,available=available,stored_months=36,temperature=4,initial_rate=94))
        other=s.scalar(select(Accession).where(Accession.code=='QH-087'))
        if not other:other=Accession(code='QH-087',crop='青豆',name='异源晚熟青豆',origin='南坡异源对照',minimum=300);s.add(other);s.flush()
        if not s.scalar(select(Lot).where(Lot.code=='QH-087-G2')):s.add(Lot(accession_id=other.id,code='QH-087-G2',generation=2,available=800,stored_months=18,temperature=-8,initial_rate=96))
        for i in range(18):
            code=chr(65+i//6)+str(i%6+1)
            if not s.scalar(select(Plot).where(Plot.code==code)):s.add(Plot(code=code,row=i//6,position=i%6,capacity=250))
        s.flush();lot=s.scalar(select(Lot).where(Lot.code=='QH-021-G3'))
        if not s.scalar(select(GerminationTest).where(GerminationTest.code=='GT-SEED-80')):s.add(GerminationTest(lot_id=lot.id,code='GT-SEED-80',sampled=100,germinated=80,state='recorded'))
        # 退种演示：一条有离库日期、三次已验收历史退种（供同作物活力拟合），一条旧单缺离库日期。
        d1=s.scalar(select(Distribution).where(Distribution.code=='DIST-DEMO-RT'))
        if not d1:
            d1=Distribution(lot_id=lot.id,code='DIST-DEMO-RT',recipient='青禾协作育种圃',seeds=500,purpose='协作圃小区性状观察后余种退回',state='received',leave_date='2026-06-01',reserve_snapshot={'leave_date':'2026-06-01','note':'演示历史签发快照'});s.add(d1);s.flush()
            for i,(days,germ) in enumerate([(90,92),(120,89),(150,85)]):
                ro=ReturnOrder(code=f'RT-DEMO-{i+1:02d}',distribution_id=d1.id,state='accepted',leave_days=days,retest_sampled=50,retest_germinated=round(50*germ/100),prediction={'decision':'pass','crop':'青豆','pass_threshold_pct':80})
                s.add(ro);s.flush()
                child=Lot(accession_id=lot.accession_id,code=f'RT-DEMO-{i+1:02d}-G{lot.generation}',generation=lot.generation,available=100,stored_months=round(36+days/30,3),temperature=lot.temperature,initial_rate=float(germ),parent_lot_id=lot.id)
                s.add(child);s.flush()
                ro.accepted_lot_id=child.id
                ro.basis={'distribution':{},'origin_lot':{},'accepted_lot':{},'leave_days':days,'note':'演示验收依据'}
                s.add(ReturnBag(return_order_id=ro.id,bag_no=f'D{i+1}-1',seeds=100,sampled=50,germinated=round(50*germ/100),state='accepted'))
        d2=s.scalar(select(Distribution).where(Distribution.code=='DIST-LEGACY-RT'))
        if not d2:
            d2=Distribution(lot_id=lot.id,code='DIST-LEGACY-RT',recipient='老协作点',seeds=120,purpose='历史纸质单余种退回，离库日期缺失',state='received',leave_date=None,reserve_snapshot={'note':'旧单无离库日期'});s.add(d2);s.flush()
            ro=ReturnOrder(code='RT-LEGACY-01',distribution_id=d2.id,state='isolated',leave_days=None,prediction={'decision':'missing_leave_date','decision_reason':'旧共享单缺离库日期，无法计算离库天数，隔离补测','crop':'青豆','pass_threshold_pct':80})
            s.add(ro);s.flush()
            s.add(ReturnBag(return_order_id=ro.id,bag_no='OLD-1',seeds=80,state='isolated'))
        s.commit();return {cls.__tablename__:s.scalar(select(func.count()).select_from(cls))for cls in (User,Accession,Lot,GerminationTest,Regeneration,Plot,Flowering,Pollination,Harvest,Distribution,ReturnOrder,ReturnBag)}
