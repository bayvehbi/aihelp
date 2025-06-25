import boto3
import os
import time
import re
from datetime import datetime, timezone
import config  # ← Burada config import ettik

CHECK_INTERVAL = 2  # seconds
DOWNLOAD_DIR = 'downloads'

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
SCREENSHOT_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}

# S3 client, config'den region çekiyoruz
s3 = boto3.client('s3', region_name=config.AWS_REGION)
BUCKET_NAME = config.S3_BUCKET_NAME

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def clear_download_folder():
    if os.path.exists(DOWNLOAD_DIR):
        for root, dirs, files in os.walk(DOWNLOAD_DIR, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for folder in dirs:
                os.rmdir(os.path.join(root, folder))
    os.makedirs(os.path.join(DOWNLOAD_DIR, 'audio'), exist_ok=True)
    os.makedirs(os.path.join(DOWNLOAD_DIR, 'screenshots'), exist_ok=True)
    os.makedirs(os.path.join(DOWNLOAD_DIR, 'others'), exist_ok=True)

def list_s3_files_with_timestamps():
    keys_with_time = {}
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=BUCKET_NAME):
        for obj in page.get('Contents', []):
            keys_with_time[obj['Key']] = obj['LastModified']
    return keys_with_time

def download_file(key):
    extension = os.path.splitext(key)[1].lower()
    if extension in AUDIO_EXTENSIONS:
        target_folder = 'audio'
    elif extension in SCREENSHOT_EXTENSIONS:
        target_folder = 'screenshots'
    else:
        target_folder = 'others'

    safe_filename = sanitize_filename(os.path.basename(key))
    target_path = os.path.join(DOWNLOAD_DIR, target_folder, safe_filename)

    print(f"Downloading {key} → {target_path}")
    s3.download_file(BUCKET_NAME, key, target_path)

def main():
    print(f"Watching bucket: {BUCKET_NAME}")

    clear_download_folder()
    program_start_time = datetime.now(timezone.utc)
    downloaded_keys = set()

    while True:
        time.sleep(CHECK_INTERVAL)
        files = list_s3_files_with_timestamps()

        for key, last_modified in files.items():
            if last_modified > program_start_time and key not in downloaded_keys:
                try:
                    download_file(key)
                    downloaded_keys.add(key)
                except Exception as e:
                    print(f"Failed to download {key}: {e}")

if __name__ == '__main__':  # ← Burada da typo fix: _name_ değil __name__
    main()
