from openai import OpenAI
import httpx
from PIL import Image
import base64
import io
from config import OPENAI_API_KEY, MAX_IMAGE_SIZE

class AIAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client())
        
    def analyze_image(self, image_path, existing_metadata=None):
        try:
            # Open and resize image
            with Image.open(image_path) as img:
                img.thumbnail(MAX_IMAGE_SIZE)
                
                # Convert to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Build prompt with existing metadata context
            context = ""
            if existing_metadata:
                people = existing_metadata.get('people', [])
                keywords = existing_metadata.get('keywords', [])
                if people:
                    context += f"Known people in image: {', '.join(people)}. "
                if keywords:
                    context += f"Existing keywords: {', '.join(keywords)}. "
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{context}Analyze this image and provide: 1) A brief description, 2) Keywords for Lightroom (comma-separated), 3) Any people or faces visible. Format as JSON with keys: description, keywords, people"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ]
            )
            
            # Parse response
            import json
            result_text = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to text parsing
            try:
                result = json.loads(result_text)
            except:
                # Fallback: create structured data from text
                result = {
                    'description': result_text,
                    'keywords': [],
                    'people': []
                }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing image: {e}")
            return {}
