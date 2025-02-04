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

def query_llm(prompt: str) -> str:
    """
    Sends the prompt to the LLM API endpoint (with streaming disabled)
    and returns the model's complete response.
    
    It prepends instructions to generate plain text output suitable for Telegram.
    Also, it post-processes the answer to remove any <think> tags.
    """
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
        # Optionally, you could also remove LaTeX blocks if necessary:
        # answer = re.sub(r"\\\[.*?\\\]", "", answer, flags=re.DOTALL)

        return answer.strip()

    except requests.exceptions.RequestException as e:
        logger.error("Error calling the LLM API: {}", e)
        return "❌ Error: Could not connect to the LLM API."
    except Exception as ex:
        logger.error("Unexpected error: {}", ex)
        return "❌ Error: An unexpected error occurred."
