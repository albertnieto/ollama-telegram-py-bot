import os
import re
import requests
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env
load_dotenv()

# Read configuration from environment variables.
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-r1")
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"

# Global variable to track LLM availability
_llm_available = None

def check_llm_availability():
    """
    Check if the Ollama LLM is available and responding.
    Returns True if available, False otherwise.
    """
    global _llm_available
    
    # If OLLAMA_ENABLED is False, don't even try
    if not OLLAMA_ENABLED:
        logger.info("Ollama integration is disabled via configuration.")
        _llm_available = False
        return False
    
    # If we've already checked and LLM is disabled, no need to check again
    if _llm_available is False:
        return False
        
    try:
        # Use a simple health check if available, or a minimal query
        logger.info(f"Testing connection to Ollama at {OLLAMA_API_URL}")
        
        # Try a minimal request
        payload = {
            "model": MODEL_NAME,
            "prompt": "test",
            "stream": False
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        # If we get here, the LLM is available
        logger.info("Successfully connected to Ollama LLM")
        _llm_available = True
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Ollama LLM: {e}")
        _llm_available = False
        return False
    except Exception as ex:
        logger.error(f"Unexpected error checking Ollama availability: {ex}")
        _llm_available = False
        return False
    
def query_llm(prompt: str) -> str:
    """
    Sends the prompt to the LLM API endpoint (with streaming disabled)
    and returns the model's complete response.
    
    It prepends instructions to generate plain text output suitable for Telegram.
    Also, it post-processes the answer to remove any <think> tags.
    
    If Ollama is disabled or unavailable, returns a fallback message.
    """
    global _llm_available
    
    # Check if we need to test LLM availability
    if _llm_available is None:
        _llm_available = check_llm_availability()
    
    # If LLM is not available, return a fallback message
    if not _llm_available:
        return "Lo siento, la función de LLM no está disponible actualmente."
    
    try:
        # Inject instruction so the answer is plain text without markdown/latex or <think> tags.
        instruction = (
            "Please provide your answer in plain text suitable for Telegram. "
            "Do not include any formatting tags (like <think>) or LaTeX code or markdown. "
        )
        full_prompt = instruction + prompt

        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False  # Instruct the API not to stream responses.
        }
        logger.debug("Sending payload: {}", payload)
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        logger.debug("Received response: {}", response)
        response.raise_for_status()

        data = response.json()
        answer = data.get("response", "No 'response' field found in the returned JSON.")
        logger.debug("Parsed response JSON: {}", data)

        # Remove any <think>...</think> blocks from the answer
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL)
        
        return answer.strip()

    except requests.exceptions.RequestException as e:
        logger.error("Error calling the LLM API: {}", e)
        # Disable LLM for future queries if there's a connection error
        _llm_available = False
        return "❌ Error: Could not connect to the LLM API. LLM functionality has been disabled."
    except Exception as ex:
        logger.error("Unexpected error: {}", ex)
        return "❌ Error: An unexpected error occurred."