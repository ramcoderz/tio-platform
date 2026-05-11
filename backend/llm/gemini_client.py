import os
import asyncio
from typing import Optional
import google.generativeai as genai
from backend.config.settings import get_settings

settings = get_settings()

class GeminiClient:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
        else:
            self.model = None

    async def analyze_image(self, image_path: str, prompt: str) -> Optional[str]:
        if not self.model:
            return None
        try:
            import PIL.Image
            img = PIL.Image.open(image_path)
            response = await asyncio.to_thread(self.model.generate_content, [prompt, img])
            return response.text
        except Exception as e:
            print(f"Gemini Vision Error: {e}")
            return None

    async def generate(self, prompt: str) -> str:
        if not self.model:
            return "Gemini API key not configured."
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            return f"[Gemini Error: {e}]"

    async def generate_stream(self, prompt: str):
        if not self.model:
            yield "Gemini API key not configured."
            return
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt, stream=True)
            for chunk in response:
                yield chunk.text
        except Exception as e:
            yield f"[Gemini Stream Error: {e}]"

gemini_client = GeminiClient()
