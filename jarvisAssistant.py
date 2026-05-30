from dotenv import load_dotenv
import os
from google import genai
from google.genai import types
import sounddevice as sd
from openwakeword.model import Model


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

GEMINI_PROMPT = """
You are an onboard manufacturing assistant operating in a Toyota production environment.

Listen to the worker's statement.
Determine whether the worker is reporting a defect severity.

If the worker says or implies a standard defect, return: 1
If the worker says or implies a critical defect, return: 2


Return only a single digit:
1 for defect
2 for critical defect
Do not return any other text.
Do not explain your reasoning.
Do not include punctuation, labels, or formatting.
If both "defect" and "critical" are present, return:
2

Examples:

Worker:
"Hey Toyota, this part has a defect."

Output:
1

Worker:
"Hey Toyota, defect on this component."

Output:
1

Worker:
"Hey Toyota, QR 4512 has a defect."

Output:
1

Worker:
"Hey Toyota, this is a critical defect."

Output:
2

Worker:
"Hey Toyota, critical issue on this part."

Output:
2

Worker:
"Hey Toyota, QR 7821 has a critical defect."

Output:
2

Worker:
"Hey Toyota, this part is defective."

Output:
1

Worker:
"Hey Toyota, this is a critical manufacturing defect."

Output:
2

Output only:
1
or
2

"""



recording_duration = 5 # seconds
sample_rate = 16000
wake_threshold = 0.3
chunk_size = 1280 # 1280 samples at 16kHz = 80ms
gemini_temp = 0.1 # low temp = more predictable, safer for robotics control

def detect_code():
    return

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
                detect_code()
                oww_model.reset()  # prevent multiple triggers
                return



def main():
    while True:
        listen_for_wake_word()


if __name__ == "__main__":
    main()
