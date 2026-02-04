## HLS
1. HLS(HTTP Live Streaming): HTTP 기반의 적응형 비트레이트 스트리밍 프로토콜로, 영상을 작은 조각(세그먼트)으로 나눠 일반 웹 서버를 통해 전송합니다.
2. 비트레이트: 1초당 처리하거나 전송되는 데이터(비트)의 양을 나타내는 수치

``` mermaid
flowchart TB
    subgraph Local_Test
        subgraph STORAGE["localstack:S3"]
            UPLOAD_BUCKET[("Upload Bucket")]
            HLS_BUCKET[("HLS Bucket")]
        end
    
        subgraph EncodingCluster["인코딩 서버 클러스터"]
            direction TB
            WORKER1["Worker 1<br/>(FFmpeg)"]
            WORKER2["Worker 2<br/>(FFmpeg)"]
            WORKER_N["Worker N<br/>(FFmpeg)"]
            SCHEDULER["작업 스케줄러 - Watcher <br/>(파일 감시 및 유휴 자원 관리)"]
            
            subgraph HLS_SERVER["HLS 인코딩 서버"]
                INCO_SEVER1["tasks"]
                INCO_SEVER2["tasks"]
                INCO_SEVER3["tasks"]
            end
        end

        subgraph CDN["MOCK_CDN"]
            CDN_IND["nginx"]
        end

        subgraph EC2["사용자 서비스"]
            
            subgraph Management["관리 시스템"]
                API["관리 API 서버"]
                DB[("PostgreSQL<br/>상태 관리")]
            end

            subgraph CLIENT["모니터링"]
                CL_SERVICE["HLS Encoding Server Monitoring"]                
            end
        end
    end
    
    UPLOAD_BUCKET -->|신규 파일 감지| SCHEDULER
  
    SCHEDULER -->|분배| WORKER1
    SCHEDULER -->|분배| WORKER2
    SCHEDULER -->|분배| WORKER_N
   
    WORKER1 --> INCO_SEVER1
    WORKER2 --> INCO_SEVER2
    WORKER_N --> INCO_SEVER3
    
 
    INCO_SEVER1 -->|인코딩 업로드| HLS_BUCKET
    INCO_SEVER2 -->|인코딩 업로드| HLS_BUCKET
    INCO_SEVER3 -->|인코딩 업로드| HLS_BUCKET
    INCO_SEVER1 -->|상태 저장| DB
    INCO_SEVER2 -->|상태 저장| DB
    INCO_SEVER3 -->|상태 저장| DB

    HLS_BUCKET -->|배포 등록| CDN
    API --> |HLS 모니터링 데이터| CL_SERVICE
    CDN -->|.ts & .m3u8 전송| CL_SERVICE
    DB -->|상태 전달| API
```

## 코드
[GIT 코드](https://github.com/MHT-DEV/VR-SHOWROOM-HLS-TEST/tree/main/infra)

## 컨테이너 환경
- localstack(s3):4566
- redis:6379
- postgres:5432
- nginx:80
    - admin api 서버:8000
- watcher
- worker1, 2

## 서비스 프로세스

### 1. S3 파일 등록
### 2. watcher/watcher.py S3 파일 감지
- worker cpu + memory 상태 측정
- 영상 ETag(해시 코드), 이름으로 중복 방지 (Redis)
- 폴링을 통한 S3 감시
### 3. worker/tasks.py 인코딩
- 작업 시작 시 lock
- 인코딩 프로세스
    - upload-bucket 다운 -> 로컬 저장소 -> 인코딩 -> hls-bucket 업로드

    - 기본 인코딩 커멘드
        - ```
          return [
               "ffmpeg", "-i", local_from,
               "-c:v", "libx264", "-preset", "medium", "-crf", "23",
               "-c:a", "aac", "-b:a", "128k",
               "-g", "60",
               "-keyint_min", "60",
               "-sc_threshold", "0",
               "-force_key_frames", "expr:gte(t,n_forced*2)",
               "-hls_flags", "independent_segments",
               "-avoid_negative_ts", "make_zero",
               "-f", "hls",
               "-hls_time", "2",
               "-hls_list_size", "0",
               "-hls_segment_filename", f"{local_to}/output_%d.ts",
               "-hls_playlist_type", "vod",
               output_playlist, "-y"
           ]

    - 화질 별 인코딩 커멘드
        - ```
          ffmpeg -benchmark -y -i storage/input_file.mp4 \
          -map 0:v:0 -c:v:0 libx264 -s:0 640x360 -b:v:0 800k -maxrate:v:0 800k -bufsize:v:0 1600k \
          -map 0:a:0 -c:a:0 aac -b:a:0 96k \
          -map 0:v:0 -c:v:1 libx264 -s:1 1280x720 -b:v:1 2800k -maxrate:v:1 2800k -bufsize:v:1 5600k \
          -map 0:a:0 -c:a:1 aac -b:a:1 128k \
          -map 0:v:0 -c:v:2 libx264 -s:2 1920x1080 -b:v:2 5000k -maxrate:v:2 5000k -bufsize:v:2 10000k \
          -map 0:a:0 -c:a:2 aac -b:a:2 192k \
          -map 0:v:0 -c:v:3 libx264 -s:3 2560x1440 -b:v:3 10000k -maxrate:v:3 10000k -bufsize:v:3 20000k \
          -map 0:a:0 -c:a:3 aac -b:a:3 192k \
          -map 0:v:0 -c:v:4 libx264 -s:4 3840x2160 -b:v:4 20000k -maxrate:v:4 20000k -bufsize:v:4 40000k \
          -map 0:a:0 -c:a:4 aac -b:a:4 256k \
          -preset ultrafast -g 60 -sc_threshold 0 -keyint_min 60 \
          -force_key_frames expr:gte(t,n_forced*2) \
          -f hls -hls_time 2 -hls_list_size 0 -hls_playlist_type vod -hls_flags independent_segments \
          -master_pl_name master.m3u8 \
          -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:2 v:3,a:3 v:4,a:4" \
          -hls_segment_filename "storage/tmp_workdir/%v/%d.ts" \
          "storage/tmp_workdir/%v/index.m3u8"

- 옵션 master.m3u8 동적 생성(화질 master.m3u8별도 보유) 예시
    - ```
        #EXTM3U
        #EXT-X-VERSION:3
        
        #EXT-X-STREAM-INF:BANDWIDTH=2000000,NAME="1bb811fd-497e-4ee2-963c-5a2bcf4440c7.mov"
        1bb811fd-497e-4ee2-963c-5a2bcf4440c7.mov/output.m3u8
        
        #EXT-X-STREAM-INF:BANDWIDTH=2000001,NAME="44852342-8950-42d7-ab07-a5759ee59126.mp4"
        44852342-8950-42d7-ab07-a5759ee59126.mp4/output.m3u8
        
        #EXT-X-STREAM-INF:BANDWIDTH=2000002,NAME="4fb050fa-85bb-4186-8783-36940234de43.mov"

- S3 Bucket 구조
    - ```
      encode/master.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/master.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/0/0~n.ts
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/0/index.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/1/0~n.ts
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/1/index.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/2/0~n.ts
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/2/index.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/3/0~n.ts
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/3/index.m3u8
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/4/0~n.ts
      encode/28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/4/index.m3u8

- #### 구조 도식화

    - ``` mermaid
      graph TD
          Root([S3 Bucket]) --> Encode[encode/]
        
          Encode --> MasterMain[master.m3u8 <br/><i>- 전체 영상 목록 관리</i>]
          Encode --> VideoDir[28dbd38f-ddd9-46a0-a4b2-1f2014e7b3e4.mov/]
        
          subgraph VideoContent [Video HLS Package]
              VideoDir --> MasterSub[master.m3u8 <br/><i>- 해당 영상의 화질 메타 데이터</i>]
            
              VideoDir --> Dir0[0/ <br/>360p]
              VideoDir --> Dir1[1/ <br/>720p]
              VideoDir --> Dir2[2/ <br/>1080p]
              VideoDir --> Dir3[3/ <br/>1440p]
              VideoDir --> Dir4[4/ <br/>4K]
            
              Dir0 --> Idx0[index.m3u8]
              Dir0 --> Seg0[0.ts, 1.ts, ... n.ts]
            
              Dir1 --> Idx1[index.m3u8]
              Dir1 --> Seg1[0.ts, 1.ts, ... n.ts]
            
              Dir2 --> Idx2[index.m3u8]
              Dir2 --> Seg2[0.ts, 1.ts, ... n.ts]
            
              Dir3 --> Idx3[index.m3u8]
              Dir3 --> Seg3[0.ts, 1.ts, ... n.ts]
            
              Dir4 --> Idx4[index.m3u8]
              Dir4 --> Seg4[0.ts, 1.ts, ... n.ts]
          end

### 4. Admin API
- worker와 상태 DB 공용으로 사용
- 임시 파일 업로드, 비디오 상태, 인코딩 정보, 작업자 정보 등 상태 관리
- FastAPI 구현

### 5. 사용자 서비스
- hls.js 영상 재생
- 매니페스트를 덮어쓰는 스트리밍 동적 트랙 구현



