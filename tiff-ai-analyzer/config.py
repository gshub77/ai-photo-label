import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SUPPORTED_FORMATS = ['.tiff', '.tif']
MAX_IMAGE_SIZE = (1024, 1024)  # Resize for AI analysis
