from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import Settings
from app.manager.api import endpoints
from app.core.database import Base, engine
from app.services.db_service import set_service_type
from app.services.s3_service import S3Service

set_service_type('api')

Base.metadata.drop_all(bind=engine)

app = FastAPI(title="Video Transcoder API")

s3_service = S3Service()
s3_service.set_cors_policy_for_uploads(Settings.UPLOAD_BUCKET_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 경로 등록
app.include_router(endpoints.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "Video Transcoder API is running"}