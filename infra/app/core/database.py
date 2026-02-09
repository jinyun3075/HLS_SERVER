from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import Settings
from celery.signals import worker_process_init

# 전역 변수로 엔진과 세션 선언
engine = None
api_engine = None
SessionLocal = None
SessionLocalApi = None
Base = declarative_base()

def setup_database_connections():
    global engine, api_engine, SessionLocal, SessionLocalApi

    pool_settings = {
        "pool_size": Settings.DB_POOL_SIZE,
        "max_overflow": Settings.DB_MAX_OVERFLOW,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }

    # Worker용 엔진
    engine = create_engine(Settings.DB_URL, **pool_settings)

    # API 서버용 엔진
    api_engine = create_engine(Settings.DB_URL, **pool_settings)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    SessionLocalApi = sessionmaker(autocommit=False, autoflush=False, bind=api_engine, expire_on_commit=False)

@worker_process_init.connect
def on_worker_process_init(**kwargs):
    print("Celery worker process initialized, setting up new database connections.")
    setup_database_connections()

# 애플리케이션 초기 로드 시 한 번 실행
setup_database_connections()


def get_session(session_type : str = 'worker'):
    return SessionLocal if session_type == 'worker' else SessionLocalApi

def get_api_db():
    db = SessionLocalApi()
    try:
        yield db
    finally:
        db.close()
