import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from a .env file if present

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")
