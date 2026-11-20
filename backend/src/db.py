import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
_url=os.environ['DATABASE_URL']
# 生产 MySQL 固定 READ COMMITTED；SQLite（本地测试）经 URL 参数指定其支持的级别。
_opts={'pool_pre_ping':True}
if not _url.startswith('sqlite'):_opts['isolation_level']='READ COMMITTED'
engine=create_engine(_url,**_opts)
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
def session():
    with Session() as s:yield s
