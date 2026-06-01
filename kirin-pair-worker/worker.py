"""
Kirin Pair Worker - Background Media Processing Worker
Handles media processing tasks via Redis queue, using ffmpeg for conversion
and potentially calling whisper-service for transcription.
"""
import os
import json
import time
import logging
import subprocess
from typing import Dict, Any
import redis
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
WORKER_QUEUE = os.getenv("WORKER_QUEUE", "kirin:worker:queue")
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper-service:8003")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")
FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "300"))  # 5 minutes default

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True
)

# Initialize HTTP client for whisper-service
http_client = httpx.Client(timeout=30.0)

def process_media_conversion(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert media file using ffmpeg
    Expected task_data: {
        "task_type": "media_conversion",
        "input_file": "/path/to/input.mp4",
        "output_file": "/path/to/output.wav",
        "format_params": ["-ar", "16000", "-ac", "1", "-vn"]  # Example for audio extraction
    }
    """
    input_file = task_data.get("input_file")
    output_file = task_data.get("output_file")
    format_params = task_data.get("format_params", [])
    
    if not input_file or not output_file:
        raise ValueError("Missing input_file or output_file in task data")
    
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", "-i", input_file] + format_params + [output_file]
    
    logger.info(f"Running ffmpeg conversion: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr}")
            raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
        
        logger.info(f"Conversion successful: {input_file} -> {output_file}")
        return {
            "status": "success",
            "input_file": input_file,
            "output_file": output_file,
            "command": " ".join(cmd)
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg timeout after {FFMPEG_TIMEOUT} seconds")
        raise RuntimeError(f"FFmpeg timeout after {FFMPEG_TIMEOUT} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {str(e)}")
        raise

def process_transcription(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send audio file to whisper-service for transcription
    Expected task_data: {
        "task_type": "transcription",
        "audio_file": "/path/to/audio.wav",
        "language": "pt"  # Optional
    }
    """
    audio_file = task_data.get("audio_file")
    language = task_data.get("language", "pt")
    
    if not audio_file or not os.path.exists(audio_file):
        raise ValueError(f"Audio file not found or not specified: {audio_file}")
    
    logger.info(f"Sending {audio_file} to whisper-service for transcription")
    
    try:
        with open(audio_file, "rb") as f:
            files = {"file": (os.path.basename(audio_file), f, "audio/wav")}
            data = {"language": language}
            
            response = http_client.post(
                f"{WHISPER_URL}/transcribe",
                files=files,
                data=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Transcription successful: {len(result.get('text', ''))} characters")
            return {
                "status": "success",
                "audio_file": audio_file,
                "transcription": result.get("text", ""),
                "language": result.get("language", language),
                "segments": result.get("segments", [])
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Whisper-service HTTP error: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"Whisper-service error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {str(e)}")
        raise

def main():
    """Main worker loop - listen to Redis queue and process tasks"""
    logger.info(f"Kirin Pair Worker started")
    logger.info(f"Listening to queue: {WORKER_QUEUE}")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    logger.info(f"Whisper service: {WHISPER_URL}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    
    processed_count = 0
    error_count = 0
    
    try:
        while True:
            try:
                # Blocking pop from Redis queue with timeout
                _, task_json = redis_client.brpop(WORKER_QUEUE, timeout=30)
                
                if task_json is None:
                    # Timeout - just continue looping
                    logger.debug("Redis brpop timeout, continuing...")
                    continue
                
                logger.info(f"Received task: {task_json[:100]}...")
                
                try:
                    task_data = json.loads(task_json)
                    task_type = task_data.get("task_type")
                    
                    result = None
                    if task_type == "media_conversion":
                        result = process_media_conversion(task_data)
                    elif task_type == "transcription":
                        result = process_transcription(task_data)
                    else:
                        logger.warning(f"Unknown task type: {task_type}")
                        result = {
                            "status": "skipped",
                            "reason": f"Unknown task type: {task_type}"
                        }
                    
                    if result and result.get("status") == "success":
                        processed_count += 1
                        logger.info(f"Task processed successfully ({processed_count} total)")
                        
                        # Optionally publish result to another queue or callback
                        # For now, just log
                        
                    else:
                        error_count += 1
                        logger.warning(f"Task completed with issues: {result}")
                        
                except json.JSONDecodeError as e:
                    error_count += 1
                    logger.error(f"Invalid JSON in task: {str(e)}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing task: {str(e)}", exc_info=True)
                    
            except redis.ConnectionError as e:
                logger.error(f"Redis connection error: {str(e)}")
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {str(e)}", exc_info=True)
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in worker: {str(e)}", exc_info=True)
    finally:
        http_client.close()
        redis_client.close()
        logger.info(f"Worker shutting down. Processed: {processed_count}, Errors: {error_count}")

if __name__ == "__main__":
    main()
