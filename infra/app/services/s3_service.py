import boto3, os, mimetypes
from botocore.exceptions import ClientError

from app.core.config import Settings
from fastapi import UploadFile

class S3Service:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=Settings.S3_ENDPOINT,
            aws_access_key_id=Settings.AWS_ACCESS_KEY,
            aws_secret_access_key=Settings.AWS_SECRET_KEY,
            region_name="us-east-1"
        )

    def list_videos(self, bucket: str, prefix: str = ""):
        response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        video_files = []

        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                etag = obj['ETag'].replace('"', '')

                mime_type, _ = mimetypes.guess_type(key)
                if mime_type and mime_type.startswith('video/'):
                    video_files.append({"Key":key,"ETag":etag})

        return video_files

    def download_file(self, bucket: str, key: str, local_path: str):
        self.s3.download_file(bucket, key, local_path)

    def upload_hls_folder(self, local_folder: str, bucket: str, s3_prefix: str):
        for root, _, files in os.walk(local_folder):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_folder)
                s3_key = os.path.join(s3_prefix, relative_path).replace("\\", "/")
                self.s3.upload_file(local_file_path, bucket, s3_key)

    async def upload_api_file(self, file: UploadFile, bucket: str,  s3_path: str):
        try:
            self.s3.upload_fileobj(
                file.file,
                bucket,
                s3_path,
                ExtraArgs={"ContentType": file.content_type}
            )
        except Exception as e:
            return str(e)

    def update_master_file(self, bucket: str, s3_prefix: str ='encode/'):
        bucket_list = self.s3.list_objects_v2(Bucket=bucket, Prefix=s3_prefix, Delimiter='/')

        prefixes = [content.get('Prefix') for content in bucket_list.get('CommonPrefixes', [])]

        if not prefixes:
            print("하위 폴더를 찾을 수 없습니다.")
            return

        master_lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            ""
        ]
        for i, p in enumerate(sorted(prefixes)):
            folder_name = p.split('/')[-2]

            bandwidth = 2000000 + i
            master_lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},NAME="{folder_name}"')
            master_lines.append(f'{folder_name}/master.m3u8')
            master_lines.append("")

        master_content = "\n".join(master_lines)

        master_key = f"{s3_prefix}master.m3u8"

        self.s3.put_object(
            Bucket=bucket,
            Key=master_key,
            Body=master_content,
            ContentType='application/x-mpegURL',
            CacheControl='no-cache, no-store, must-revalidate'
        )

    def set_cors_policy_for_uploads(self, bucket_name: str):
        cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['PUT', 'POST', 'GET'],
                    'AllowedOrigins': Settings.CORS_ORIGINS,
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        try:
            self.s3.put_bucket_cors(
                Bucket=bucket_name,
                CORSConfiguration=cors_configuration
            )
            print(f"Successfully set CORS policy for bucket '{bucket_name}' with origins: {Settings.CORS_ORIGINS}")
        except ClientError as e:
            print(f"Error setting CORS policy: {e}", flush=True)


    def create_presigned_url_for_put(self, bucket_name: str, object_key: str, expiration: int = 3600) -> str | None:
        try:
            url = self.s3.generate_presigned_url(
                'put_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expiration,
                HttpMethod='PUT'
            )
            return url
        except ClientError as e:
            print(f"Error creating presigned URL: {e}", flush=True)
        return None