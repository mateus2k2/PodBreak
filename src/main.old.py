# from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import whisperx
import torch
import os
import gc  # for garbage collection

# app = FastAPI()
# device = "cuda" if torch.cuda.is_available() else "cpu"

# class TranscriptionRequest(BaseModel):
#     file: str 
#     batch_size: int = 16 
#     compute_type: str = "float16" 
#     model_name: str = "large-v2" 
#     language: str = "pt"

# @app.post("/transcribe/")
# async def transcribe(request: TranscriptionRequest):
#     if not os.path.exists(request.file):
#         raise HTTPException(status_code=400, detail="Audio file does not exist.")

#     try:
#         # Load model temporarily
#         model = whisperx.load_model(
#             request.model_name,
#             device,
#             compute_type=request.compute_type
#         )

#         audio = whisperx.load_audio(request.file)
#         result = model.transcribe(audio, batch_size=request.batch_size, language=request.language)

#         model_a, metadata = whisperx.load_align_model(language_code=request.language, device=device)
#         result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

#         return {"segments": result["segments"]}

#     finally:
#         # Clean up to release memory
#         del model
#         if 'model_a' in locals():
#             del model_a
#         if 'metadata' in locals():
#             del metadata
#         torch.cuda.empty_cache()
#         gc.collect()


model = whisperx.load_model("base.en", "cuda", compute_type="float16")
audio = whisperx.load_audio("./data/teste.wav")
result = model.transcribe(audio, batch_size=8, language="en")

model_a, metadata = whisperx.load_align_model(language_code="en", device="cuda")
result = whisperx.align(result["segments"], model_a, metadata, audio, "cuda", return_char_alignments=False)

print(result["segments"])

