#!/bin/bash

sudo apt install ocrmypdf libgl1 poppler-utils python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate

pip install kokoro-onnx soundfile ebooklib beautifulsoup4 opencv-python pdf2image pypdf
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx