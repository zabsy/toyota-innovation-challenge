from dotenv import load_dotenv
import os
from google import genai
from google.genai import types
import sounddevice as sd
from openwakeword.model import Model


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

recording_duration = 5 # seconds
sample_rate = 16000
wake_threshold = 0.3
chunk_size = 1280 # 1280 samples at 16kHz = 80ms
gemini_temp = 0.1 # low temp = more predictable, safer for robotics control

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
            print(f"Wake word score: {score:.3f}")

            if score>wake_threshold:
                oww_model.reset()  # prevent multiple triggers
                return



def main():
    while True:
        listen_for_wake_word()


if __name__ == "__main__":
    main()
