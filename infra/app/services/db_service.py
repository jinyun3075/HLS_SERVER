from contextlib import contextmanager
from sqlalchemy.orm import Session
from app.core import Video, Worker, EncodingJob, ENTITY_TYPE
from app.core.database import SessionLocalApi, SessionLocal
from typing import Type

service_type : str = 'worker'

def set_service_type(name:str):
    global service_type
    service_type = name

@contextmanager
def session_scope():
    session = SessionLocal() if service_type == 'worker' else SessionLocalApi()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def select_all_entity(entity_class : Type[ENTITY_TYPE], db: Session = None):
    if db:
        return db.query(entity_class)
    with session_scope() as db:
        return db.query(entity_class)

def select_entity(entity_class : Type[ENTITY_TYPE], uuid : str, db: Session = None):
    if db:
        return db.query(entity_class).filter_by(id = uuid).first()
    with session_scope() as db:
        return db.query(entity_class).filter_by(id = uuid).first()

def insert_or_update_video(dto : Video, db: Session = None):
    if db:
        _perform_insert_or_update(db, Video, {"original_path": dto.original_path, "s3_etag": dto.s3_etag}, dto)
        return dto
    with session_scope() as db_session:
        _perform_insert_or_update(db_session, Video, {"original_path": dto.original_path, "s3_etag": dto.s3_etag}, dto)
        return dto

def insert_or_update_worker(dto : Worker, db: Session = None):
    if db:
        _perform_insert_or_update(db, Worker, {"hostname": dto.hostname}, dto)
        return dto
    with session_scope() as db_session:
        _perform_insert_or_update(db_session, Worker, {"hostname": dto.hostname}, dto)
        return dto

def insert_or_update_job(dto : EncodingJob, db: Session = None):
    if db:
        _perform_insert_or_update(db, EncodingJob, {"id": dto.id}, dto)
        return dto
    with session_scope() as db_session:
        _perform_insert_or_update(db_session, EncodingJob, {"id": dto.id}, dto)
        return dto

def _perform_insert_or_update(db: Session, model_class, filter_criteria, dto):
    entity = db.query(model_class).filter_by(**filter_criteria).first()
    if entity:
        update_entity(dto, entity)
    else:
        db.add(dto)
        entity = dto
    db.flush()
    db.refresh(entity)
    return entity

def update_entity(dto : ENTITY_TYPE , entity):
    for key, value in dto.__dict__.items():
        if not key.startswith('_') and value is not None:
            setattr(entity, key, value)
