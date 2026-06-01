"""
Whisper Service for Kirin Pair
Provides audio transcription using faster-whisper.
"""
import logging
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import torch
from faster_whisper import WhisperModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper Service", description="Audio transcription service for Kirin Pair")

# Load the Whisper model
# We'll use the "tiny" model for now to keep it lightweight and fast for testing.
# In production, this should be configurable via environment variable.
MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Loading Whisper model '{MODEL_SIZE}' on device '{DEVICE}'")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe an audio file.
    """
    try:
        # Save the uploaded file to a temporary location
        # In a production service, we would use a proper temporary file handling.
        # For simplicity, we'll read the file into memory.
        # Note: This is not suitable for large files, but acceptable for MVP.
        contents = await file.read()
        
        # Transcribe the audio
        segments, info = model.transcribe(
            contents, 
            beam_size=5,
            language=None,  # Auto-detect language
            vad_filter=True
        )
        
        # Collect the transcription results
        transcription = []
        for segment in segments:
            transcription.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [{"word": word.word, "start": word.start, "end": word.end, "probability": word.probability} for word in segment.words] if hasattr(segment, 'words') else []
            })
        
        result = {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "transcription": transcription
        }
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "model": MODEL_SIZE, "device": DEVICE}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8003")))
