import time
import logging
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key) if api_key else None

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> str:
        """
        Calls Gemini API to generate content with exponential backoff retries.
        """
        if not self.client:
            raise ValueError("Gemini API key is missing. Cannot generate content.")

        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config if config else None,
                )
                if response.text:
                    return response.text.strip()
                return ""
            except Exception as exc:
                logger.warning(
                    f"Gemini API attempt {attempt}/{max_retries} failed: {exc}"
                )
                if attempt == max_retries:
                    logger.error("Exhausted retries for Gemini generate_content.")
                    raise exc
                time.sleep(backoff_factor ** attempt)

        return ""
