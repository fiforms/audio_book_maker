from kokoro_onnx import Kokoro
import soundfile as sf

kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
samples, rate = kokoro.create("Hello, world!", voice="af_bella", speed=1.0, lang="en-us")
sf.write("output.wav", samples, rate)
