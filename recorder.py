from pynput import keyboard
from datetime import datetime
import os
from mss import mss
import sounddevice as sd
import soundfile as sf
import threading
import numpy as np
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Import from config.py
import config

# S3 setup
s3 = boto3.client("s3", region_name=config.AWS_REGION)
bucket_name = config.S3_BUCKET_NAME

def upload_to_s3(filepath, subfolder="audio"):
    filename = os.path.basename(filepath)
    key = f"{subfolder}/{filename}"
    try:
        s3.upload_file(filepath, bucket_name, key)
        print(f"[→] Uploaded to s3://{bucket_name}/{key}")
    except (BotoCoreError, ClientError) as e:
        print(f"[!] S3 upload failed: {e}")

# Local folders
BASE_DIR = os.path.abspath(".")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SCREEN_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(SCREEN_DIR, exist_ok=True)

# State flags
is_cmd_pressed = False
is_recording = False
audio_frames = []
audio_lock = threading.Lock()
stream = None

# Audio settings
SAMPLERATE = 44100
CHANNELS = 1

def start_recording():
    global stream, audio_frames
    print("[*] Starting audio recording...")

    def callback(indata, frames, time, status):
        if status:
            print(f"[!] Audio stream status: {status}")
        with audio_lock:
            audio_frames.append(indata.copy())

    audio_frames = []
    stream = sd.InputStream(callback=callback, channels=CHANNELS, samplerate=SAMPLERATE)
    stream.start()

def stop_recording_and_save():
    global stream, audio_frames
    print("[*] Stopping and saving audio...")
    stream.stop()
    stream.close()

    with audio_lock:
        data = np.concatenate(audio_frames, axis=0)

    filename = os.path.join(AUDIO_DIR, f"{datetime.now().isoformat()}.wav")
    sf.write(filename, data, SAMPLERATE)
    print(f"[+] Audio saved: {filename}")
    upload_to_s3(filename, subfolder="audio")

def take_screenshot():
    filename = os.path.join(SCREEN_DIR, f"{datetime.now().isoformat()}.png")
    try:
        print("[*] Taking screenshot...")
        with mss() as sct:
            sct.shot(output=filename)
        print(f"[+] Screenshot saved: {filename}")
        upload_to_s3(filename, subfolder="screenshots")
    except Exception as e:
        print(f"[!] Screenshot error: {e}")

def on_press(key):
    global is_cmd_pressed, is_recording

    print(f"[>] Key pressed: {key}")

    if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
        is_cmd_pressed = True

    elif key == keyboard.Key.right and is_cmd_pressed:
        if not is_recording:
            is_recording = True
            threading.Thread(target=start_recording).start()
        else:
            is_recording = False
            threading.Thread(target=stop_recording_and_save).start()

    elif key == keyboard.Key.left and is_cmd_pressed:
        threading.Thread(target=take_screenshot).start()

def on_release(key):
    global is_cmd_pressed
    if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
        is_cmd_pressed = False

print("[*] Running... Use:")
print("    Cmd + → to start/stop microphone recording")
print("    Cmd + ← to take a screenshot and upload to S3")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
