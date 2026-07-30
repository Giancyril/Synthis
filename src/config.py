import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    def __init__(self, check_keys: bool = True):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        if check_keys:
            self.validate()

    def validate(self):
        missing = []
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Please set them in your .env file or environment."
            )


# Default singleton instance (validates on import unless explicitly overridden)
config = Config(check_keys=False)
