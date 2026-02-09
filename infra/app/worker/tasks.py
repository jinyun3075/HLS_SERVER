import m3u8, psutil, shutil, os, subprocess, threading, re, time

from celery.signals import worker_ready
from app.core import Video, EncodingJob, Settings, Worker
from app.core.enum import VideoStatus, JobStatus, WorkerStatus
from app.worker.celery_app import celery_app
from app.worker.redis_app import watch_state
from app.services.s3_service import S3Service
from app.services.db_service import (
    insert_or_update_video, insert_or_update_job, insert_or_update_worker, select_entity, session_scope, update_job_progress
)

s3_service = S3Service()

LOCK_KEY_PREFIX = "lock:worker:"
LOCK_EXPIRATION_SECONDS = 1800
MASTER_COUNT_PREFIX ="count:master:"

def _get_duration(file_path: str) -> float:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Error getting video duration: {e}", flush=True)
        return 0.0

def _parse_time_to_seconds(time_str: str) -> float:
    try:
        h, m, s = map(float, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0.0

@celery_app.task(name="encode_hls_task", bind=True)
def process_encode(self, video_id : str, job_id: str):
    lock_key = f"{LOCK_KEY_PREFIX}{Settings.WORKER_NAME}"
    is_lock_acquired = watch_state.set(lock_key, "BUSY", nx=True, ex=LOCK_EXPIRATION_SECONDS)

    if not is_lock_acquired:
        print(f"30초 후 재시도합니다. (Task ID: {self.request.id})", flush=True)
        raise self.retry(countdown=30, max_retries=120)

    try:
        with session_scope() as db:
            s3_upload_video = select_entity(Video, video_id, db = db)
            current_job = select_entity(EncodingJob, job_id, db = db)

            print(f"--- [작업 시작] 파일: {s3_upload_video.original_path} ---", flush=True)
            encode_hls(s3_upload_video, current_job, db)
            print(f"--- [작업 완료] {s3_upload_video.original_path} 처리 끝 ---", flush=True)

    finally:
        watch_state.delete(lock_key)

def encode_hls(s3_upload_video : Video, current_job: EncodingJob, db):
    print(f"--- [인코딩 시작] {s3_upload_video.filename}---", flush=True)
    base_name = s3_upload_video.filename
    work_dir = f"storage/tmp_{base_name.split('.')[0]}"
    input_local = f"storage/{base_name}"

    os.makedirs(work_dir, exist_ok=True)

    for i in range(6):
        target_dir = os.path.join(work_dir, str(i))
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

    try:
        s3_service.download_file(Settings.UPLOAD_BUCKET_NAME, s3_upload_video.original_path, input_local)

        watch_state.incr(MASTER_COUNT_PREFIX)

        total_duration = _get_duration(input_local)
        if total_duration == 0:
            raise ValueError("Could not determine video duration.")

        current_job.status = JobStatus.ENCODING
        insert_or_update_job(current_job, db=db)

        command = convert_default_hls_command(input_local, work_dir)
        process = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding='utf-8')

        last_progress = -1

        for line in process.stderr:
            match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
            if match:
                current_time = _parse_time_to_seconds(match.group(1))
                progress = int((current_time / total_duration) * 100)
                if progress > last_progress:
                    last_progress = progress
                    update_job_progress(current_job.id, min(progress, 100))
                    print(f"  [진행률] {min(progress, 100)}%", flush=True)

        process.wait()
        master_path = f"{work_dir}/master.m3u8"
        s3_prefix = f"encode/{base_name}"

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stderr=process.stderr.read())

        encode_status = verify_encode(master_path)

        if encode_status.get("is_valid") is True:

            s3_service.upload_hls_folder(work_dir, Settings.HLS_BUCKET_NAME, s3_prefix)

            remaining_workers = watch_state.decr(MASTER_COUNT_PREFIX)
            if remaining_workers == 0:
                s3_service.update_master_file(Settings.HLS_BUCKET_NAME)
                watch_state.delete(MASTER_COUNT_PREFIX)
            elif remaining_workers < 0:
                watch_state.delete(MASTER_COUNT_PREFIX)

            s3_upload_video.hls_path = s3_prefix
            s3_upload_video.status = VideoStatus.READY
            current_job.status = JobStatus.SUCCESS
            current_job.progress = 100
        else:
            s3_upload_video.status = VideoStatus.VALIDATION_FAILED
            current_job.status = JobStatus.FAILED
            current_job.error_log = "Segment validation failed"

        s3_upload_video.encoding_json = encode_status

    except (subprocess.CalledProcessError, ValueError) as e:
        current_job.status = JobStatus.FAILED
        current_job.error_log = str(e)
        s3_upload_video.status = VideoStatus.ENCODING_FAILED
    except Exception as e:
        current_job.status = JobStatus.FAILED
        current_job.error_log = str(e)
        s3_upload_video.status = VideoStatus.FAILED
    finally:
        insert_or_update_video(s3_upload_video, db=db)
        insert_or_update_job(current_job, db=db)
        if os.path.exists(input_local): os.remove(input_local)
        if os.path.exists(work_dir): shutil.rmtree(work_dir)

    print(f"--- [인코딩 종료] 상태: {s3_upload_video.status.value}---", flush=True)

def verify_encode(local_master_path: str):
    if not os.path.exists(local_master_path):
        return {"is_valid": False, "error": "Master playlist file not found"}

    try:
        master_playlist = m3u8.load(local_master_path)
        all_results = []

        if not master_playlist.playlists:
            return {"is_valid": False, "error": "No variant playlists found in master"}

        for playlist_ref in master_playlist.playlists:
            base_dir = os.path.dirname(local_master_path)
            sub_path = os.path.join(base_dir, playlist_ref.uri)

            if not os.path.exists(sub_path):
                all_results.append({"uri": playlist_ref.uri, "is_valid": False, "error": "File missing"})
                continue

            sub_pl = m3u8.load(sub_path)

            has_segments = len(sub_pl.segments) > 0
            durations_valid = all(seg.duration <= (sub_pl.target_duration + 1.5) for seg in sub_pl.segments)

            res_valid = {
                "uri": playlist_ref.uri,
                "is_end_list": sub_pl.is_endlist,
                "target_duration": sub_pl.target_duration,
                "segments_count": len(sub_pl.segments),
                "is_valid": has_segments and durations_valid
            }
            all_results.append(res_valid)

        is_all_valid = len(all_results) > 0 and \
                       all(r.get("is_valid") for r in all_results) and \
                       all(r.get("is_end_list") for r in all_results)

        return {
            "is_valid": is_all_valid,
            "variants": all_results,
            "master_version": master_playlist.version,
            "total_variants": len(all_results)
        }
    except Exception as e:
        return {"is_valid": False, "error": str(e)}

def _has_audio(file_path: str) -> bool:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", file_path
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return bool(result.stdout.strip())
    except Exception:
        return False

def convert_default_hls_command(local_from :str, local_to : str):

    has_audio = _has_audio(local_from)

    configs = [
        {"w": 640,  "h": 360,  "v_bit": "800k",  "a_bit": "96k", "buf": "1600k"},
        {"w": 1280, "h": 720,  "v_bit": "2800k", "a_bit": "128k", "buf": "5600k"},
        {"w": 1920, "h": 1080, "v_bit": "5000k", "a_bit": "192k", "buf": "10000k"},
        {"w": 2560, "h": 1440, "v_bit": "10000k", "a_bit": "192k", "buf": "20000k"},
        {"w": 3840, "h": 2160, "v_bit": "20000k", "a_bit": "256k", "buf": "40000k"},
        # {"w": 7680, "h": 4320, "v_bit": "50000k", "a_bit": "320k", "buf": "80000k"}
    ]

    command = ["ffmpeg", "-benchmark", "-y", "-i", local_from]
    var_map = []

    for idx, conf in enumerate(configs):
        command += [
            "-map", "0:v:0",
            f"-c:v:{idx}", "libx264",
            f"-s:{idx}", f"{conf['w']}x{conf['h']}",
            f"-b:v:{idx}", conf['v_bit'],
            f"-maxrate:v:{idx}", conf['v_bit'],
            f"-bufsize:v:{idx}", conf['buf']
        ]

        # 오디오가 있을 때만 매핑 추가
        if has_audio:
            command += [
                "-map", "0:a:0",
                f"-c:a:{idx}", "aac",
                f"-b:a:{idx}", conf['a_bit']
            ]
            var_map.append(f"v:{idx},a:{idx}")
        else:
            var_map.append(f"v:{idx}")

    command += [
        "-preset", "ultrafast",
        "-g", "60", "-sc_threshold", "0",
        "-keyint_min", "60",
        "-force_key_frames", "expr:gte(t,n_forced*2)",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "0",
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments",
        "-master_pl_name", "master.m3u8",
        "-var_stream_map", " ".join(var_map), # 공백으로 구분된 문자열 하나로 전달
        "-hls_segment_filename", f"{local_to}/%v/%d.ts",
        f"{local_to}/%v/index.m3u8" # 마지막 출력 경로
    ]
    return command

def get_worker_status(cpu, memory):
    if cpu > 90 or memory > 90:
        return WorkerStatus.OVERLOAD
    elif cpu > 70:
        return WorkerStatus.BUSY
    elif cpu > 50:
        return WorkerStatus.NORMAL
    else:
        return WorkerStatus.IDLE

def get_resource():
    try:
        main_process = psutil.Process(os.getpid())
        children = main_process.children(recursive=True)

        total_cpu = main_process.cpu_percent(interval=1)
        for child in children:
            try:
                total_cpu += child.cpu_percent(interval=1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        total_mem = main_process.memory_percent()
        for child in children:
            try:
                total_mem += child.memory_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        core_count = 1 if 1 > psutil.cpu_count() else psutil.cpu_count()

        normalized_cpu = total_cpu / core_count

        return normalized_cpu, total_mem
    except Exception as e:
        print(f"자원 측정 에러: {e}")
        return 0.0, 0.0

def update_status(worker, db):
    try:
        cpu, memory = get_resource()
        status_enum = get_worker_status(cpu, memory)

        worker.cpu_usage = cpu
        worker.memory_usage = memory
        worker.status = status_enum

        saved_worker = insert_or_update_worker(worker, db=db)
        current_worker_id = saved_worker.id

        status_str = status_enum.value if hasattr(status_enum, 'value') else str(status_enum)

        redis_data = {
            'cpu': cpu,
            'memory': memory,
            'id': str(current_worker_id) if current_worker_id else "",
            'status': status_str
        }
        watch_state.hset(f"status:{Settings.WORKER_NAME}", mapping=redis_data)
        watch_state.expire(f"status:{Settings.WORKER_NAME}", 10)

    except Exception as e:
        import traceback
        print(f"상태 에러 상세:\n{traceback.format_exc()}", flush=True)


def roof_update_status():
    while True:
        worker = Worker(
            hostname=Settings.WORKER_NAME,
        )
        with session_scope() as db:
            update_status(worker, db)
        time.sleep(3)


@worker_ready.connect
def start_check_thread(**kwargs):
    threading.Thread(target=roof_update_status, daemon=True).start()
