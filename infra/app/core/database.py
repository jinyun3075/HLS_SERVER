from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import Settings

# 공통 풀 설정
pool_settings = {
    "pool_size": Settings.DB_POOL_SIZE,
    "max_overflow": Settings.DB_MAX_OVERFLOW,
    "pool_timeout": 30,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
}

# Worker용 엔진
engine = create_engine(
    Settings.DB_URL,
    **pool_settings
)

# API 서버용 엔진
api_engine = create_engine(
    Settings.DB_URL,
    **pool_settings
)

Base = declarative_base()

def init_db():
    from app.core.models import Video, EncodingJob, Worker
    Base.metadata.create_all(bind=engine)
    print("DB initialized!")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
SessionLocalApi = sessionmaker(autocommit=False, autoflush=False, bind=api_engine, expire_on_commit=False)

def get_session(session_type : str = 'worker'):
    return SessionLocal if session_type == 'worker' else SessionLocalApi

def get_api_db():
    db = SessionLocalApi()
    try:
        yield db
    finally:
        db.close()
