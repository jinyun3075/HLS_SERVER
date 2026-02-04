import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core import Video, EncodingJob, Worker, Settings
from app.core.database import get_api_db
from app.manager.api.dto import ResponsePage, VideoResponse, JobResponse, WorkerResponse, VideoUploadRequest, PresignedUrlResponse
from app.services.db_service import select_all_entity
from app.services.s3_service import S3Service


s3_service = S3Service()
router = APIRouter()

def convert_page(query, page, page_size):
    if not query:
        return ResponsePage(total=0, page=page, items=[])
    
    total_count = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return ResponsePage(total=total_count, page=page, items=items)

@router.get("/videos", response_model=ResponsePage[VideoResponse])
def get_videos(page: int = 1, page_size: int = 10, db: Session = Depends(get_api_db)):
    try:
        query = select_all_entity(Video, db=db)
        return convert_page(query, page, page_size)
    except Exception as e:
        print(f"Error getting videos: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/video/upload", response_model=PresignedUrlResponse)
async def get_video_upload_url(request: VideoUploadRequest):
    allowed_extensions = ["mp4", "mov", "avi", "mkv"]
    file_ext = request.filename.split(".")[-1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="지원하지 않는 영상 형식입니다.")

    # S3에 저장될 파일 경로를 유니크하게 생성합니다.
    object_key = f"upload/{uuid.uuid4()}.{file_ext}"

    upload_url = s3_service.create_presigned_url_for_put(Settings.UPLOAD_BUCKET_NAME, object_key)
    if not upload_url:
        raise HTTPException(status_code=500, detail="업로드 URL 생성에 실패했습니다.")

    return PresignedUrlResponse(upload_url=upload_url, object_key=object_key)

@router.get("/jobs", response_model=ResponsePage[JobResponse])
def get_jobs(page: int = 1, page_size: int = 10, db: Session = Depends(get_api_db)):
    try:
        query = select_all_entity(EncodingJob, db=db)
        return convert_page(query, page, page_size)
    except Exception as e:
        print(f"Error getting jobs: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/workers", response_model=ResponsePage[WorkerResponse])
def get_workers(page: int = 1, page_size: int = 10, db: Session = Depends(get_api_db)):
    try:
        query = select_all_entity(Worker, db=db)
        return convert_page(query, page, page_size)
    except Exception as e:
        print(f"Error getting workers: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
