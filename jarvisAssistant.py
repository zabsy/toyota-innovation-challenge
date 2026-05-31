from dotenv import load_dotenv
import os
import numpy as np
from google import genai
from google.genai import types
import scipy.io.wavfile as wav
import tempfile
import webrtcvad
import sounddevice as sd
from openwakeword.model import Model
from faster_whisper import WhisperModel
# Talks to the parts database over HTTP via DB/DB_client.py (the Raspberry Pi side).
# The actual data lives in DB/parts_db.json on the laptop, managed by DB/DB_server.py.
from DB.DB_client import update_part
import hardhat_module.voiceCamera as cam


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")


sample_rate = 16000
wake_threshold = 0.3
chunk_size = 1280 # 1280 samples at 16kHz = 80ms

DEFECT_KEYWORDS = [
    "defect", "defective", "broken", "damaged",
    "faulty", "bad", "fail", "failed", "issue",
    "problem", "crack", "cracked", "scratch", "scratched",
    "wrong", "reject", "rejected"
]

def listen_for_wake_word():
    print("Waiting for 'Hey Jarvis'...")
    with sd.InputStream(
    samplerate=sample_rate, 
    channels=1, 
    dtype='int16',
    blocksize=chunk_size
    ) as stream:
        while True:
            audio_chunk,_ = stream.read(chunk_size)
            audio_flat = audio_chunk.flatten()
            prediction = oww_model.predict(audio_flat)
            score = prediction.get("hey_jarvis", 0.0)
            if score>wake_threshold:
                print("Wake Word Activated!")
                oww_model.reset()  # prevent multiple triggers
                return

def record_audio(silence_duration=0.6, max_duration=10):
    vad = webrtcvad.Vad(2)  # Aggressiveness mode (0-3)

    frame_ms = 30  # Frame size in ms (10, 20, or 30)
    frame_size = int(sample_rate * frame_ms / 1000)  # Number of samples per frame
    silent_frames = int(silence_duration * 1000 / frame_ms)
    max_frames = int(max_duration * 1000 / frame_ms)

    frames = []
    silence_counter = 0
    speech_started = False

    with sd.InputStream(
        samplerate=sample_rate, 
        channels=1, 
        dtype='int16',
        blocksize=chunk_size
    ) as stream:
        print("Recording... Speak now!")

        for _ in range(max_frames):
            audio_chunk, _ = stream.read(frame_size)
            audio_flat = audio_chunk.flatten()
            frames.append(audio_flat)


            is_speech = vad.is_speech(audio_flat.tobytes(), sample_rate)

            if is_speech:
                silence_counter = 0
                speech_started = True

            if speech_started:         
                frames.append(audio_flat)
                    
            elif speech_started:
                silence_counter += 1
                if silence_counter >= silent_frames:
                    print("Silence detected. Stopping recording.")
                    break

        audio = np.concatenate(frames).astype(np.float32) / 32768.0 
        return audio
    

def transcribe_audio(audio):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        wav.write(tmp.name, sample_rate, (audio * 32768).astype(np.int16))

    segments,_ = whisper_model.transcribe(tmp_path, beam_size=5)
    os.remove(tmp_path)

    transcript = " ".join([seg.text for seg in segments])
    print(f"Transcription: {transcript}")
    return transcript


def is_defect(transcript):
    return any(keyword in transcript.lower() for keyword in DEFECT_KEYWORDS)




def main():
    while True:
        listen_for_wake_word()

        qr_code = cam.getSerialNum()

        if qr_code is None:
            print("No part detected. Please place a part in view of the camera.")
            continue

        print(f"QR Code Detected: {qr_code}")

        audio = record_audio()
        transcript = transcribe_audio(audio)

        if not transcript.strip():
            print("No speech detected. Please try again.")
            continue

        if is_defect(transcript):
            print("Defect detected in speech. Updating database...")
            update_part(qr_code, "defect")
        else:
            print("No defect keywords detected in speech.")


if __name__ == "__main__":
    main()

cam.capture.release()