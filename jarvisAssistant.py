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
    genai_client = genai.Client(api_key=api_key)
    while True:
        listen_for_wake_word()
        print("Wake word detected! Listening for command...")
        # Here you would add code to record the user's command and send it to Gemini for processing
        # For example, you could use the same sounddevice library to record a short audio clip
        # Then you would send that audio to Gemini and get a response, which you could use to control your robot


if __name__ == "__main__":
    main()
