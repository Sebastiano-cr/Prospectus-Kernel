"""
Whisper Service - Audio Transcription Endpoint
Accepts audio file uploads and returns transcription.
For now, returns a dummy transcription. In production, integrate with a real model like faster-whisper or openai-whisper.
"""
import os
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kirin Whisper Service", description="Audio transcription service")

# In a real implementation, load your model here
# For demo, we just return a fixed string

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """
    Transcribe an audio file.
    Parameters:
    - file: audio file (wav, mp3, etc.)
    - language: optional language code (e.g., 'pt', 'en')
    Returns:
    - JSON with transcription text and metadata
    """
    logger.info(f"Received transcription request for file: {file.filename}, language: {language}")
    
    # Validate file type (optional)
    allowed_extensions = {'.wav', '.mp3', '.m4a', '.ogg', '.flac'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        logger.warning(f"File extension {ext} not in allowed list, but proceeding anyway.")
    
    # Save the file temporarily (optional, for real processing)
    # For demo, we don't actually process; just return a dummy transcription.
    # In production, you would:
    # 1. Save the uploaded file to a temporary location
    # 2. Run your Whisper model on it
    # 3. Return the result
    
    # Dummy transcription
    dummy_text = "Esta é uma transcrição de demonstração. Em produção, este serviço retornaria a transcrição real do áudio."
    
    # If you want to simulate processing time, you can add a small delay
    # await asyncio.sleep(1)
    
    return JSONResponse(
        content={
            "text": dummy_text,
            "language": language or "pt",
            "duration": 0.0,  # Placeholder
            "segments": [
                {
                    "id": 0,
                    "seek": 0,
                    "start": 0.0,
                    "end": 0.0,
                    "text": dummy_text,
                    "tokens": [],
                    "temperature": 0.0,
                    "avg_logprob": 0.0,
                    "compression_ratio": 0.0,
                    "no_speech_prob": 0.0
                }
            ]
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "whisper-service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8003")))
