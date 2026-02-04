import time, os
from app.core import Worker, Video, EncodingJob
from app.core.config import Settings
from app.worker.redis_app import watch_state
from app.worker.tasks import process_encode
from app.services.s3_service import S3Service
from app.services.db_service import insert_or_update_video, insert_or_update_worker, insert_or_update_job
from app.core.enum import VideoStatus

s3_service = S3Service()

def get_best_worker():
    keys = watch_state.keys("status:worker_*")
    best_worker = None
    min_score = 101
    for key in keys:
        com_info = watch_state.hgetall(key)
        cpu = float(com_info["cpu"])
        memory = float(com_info["memory"])
        score = (cpu + memory) / 2
        print(com_info,flush=True)
        if score < min_score:
            min_score = score
            best_worker = {
                "hostname": key.split(':')[-1],
                "id": com_info["id"],
                "status": com_info["status"]
            }


    return best_worker

def allocate_task():
    for obj in s3_service.list_videos(Settings.UPLOAD_BUCKET_NAME):
        key = obj['Key']
        etag = obj['ETag']

        saved_etag = watch_state.get(f"{Settings.REDIS_PREFIX}{key}")

        if saved_etag is None or saved_etag != etag:
            print(f"작업 추가: {key} (ETag: {etag})", flush=True)
            retry_count = 3
            while retry_count > 0:
                best_worker = get_best_worker()
                new_video = Video(
                    s3_etag = etag,
                    filename = os.path.basename(key),
                    original_path = key,
                    status = VideoStatus.ENCODING
                )
                print(f"{best_worker}....{best_worker['status']}", flush=True)
                if best_worker and best_worker['status'] != 'overload' :
                    print(f"사용 워커: {best_worker['hostname']} 상태: {best_worker['status']}", flush=True)

                    # 관리 DB 적재
                    video_object = insert_or_update_video(new_video)

                    job_object = insert_or_update_job(EncodingJob(
                        video_id = video_object.id,
                        worker_id = best_worker["id"]
                    ))

                    # JOB 할당
                    process_encode.apply_async(args=[str(video_object.id), str(job_object.id)], queue=best_worker["hostname"])

                    # 중복 방지용 저장
                    watch_state.set(f"{Settings.REDIS_PREFIX}{key}",etag)

                    break
                else:
                    retry_count -= 1
                    print(f"모든 워커의 자원이 부족합니다. 3초 후 재시도 합니다. 남은 횟수 ${retry_count}", flush=True)
                    time.sleep(3)

def watch_s3():
    print(f"S3 감시 시작 ({Settings.UPLOAD_BUCKET_NAME})...", flush=True)
    # 폴링 시작
    while True:
        try:
            allocate_task()
            time.sleep(2) # 2초마다 확인
        except Exception as e:
            print(f"에러 발생: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    watch_s3()