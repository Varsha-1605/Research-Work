

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
import os
from dotenv import load_dotenv
import time
import requests
import json
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-pro-latest")
        self.text_processor = TextProcessor(api_key)
    
    @staticmethod
    def _parse_analysis(text):
        """Parse the analysis text into structured format"""
        analysis_dict = {
            'product_name': '',
            'category': '',
            'description': '',
            'price': '',
            'key_features': [],
            'specifications': {},
            'search_keywords': []
        }
        
        try:
            # Remove BEGIN_ANALYSIS and END_ANALYSIS
            if 'BEGIN_ANALYSIS' in text and 'END_ANALYSIS' in text:
                content = text.split('BEGIN_ANALYSIS')[-1].split('END_ANALYSIS')[0].strip()
            else:
                content = text.strip()
            
            # Split into lines
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('Product Name:'):
                    analysis_dict['product_name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Category:'):
                    analysis_dict['category'] = line.split(':', 1)[1].strip()
                elif line.startswith('Description:'):
                    analysis_dict['description'] = line.split(':', 1)[1].strip()
                elif line.startswith('Price:'):
                    analysis_dict['price'] = line.split(':', 1)[1].strip()
                elif line.startswith('Key Features:'):
                    current_section = 'features'
                elif line.startswith('Specifications:'):
                    current_section = 'specifications'
                elif line.startswith('Search Keywords:'):
                    current_section = 'keywords'
                elif line.startswith('- '):
                    if current_section == 'features':
                        analysis_dict['key_features'].append(line.strip('- '))
                    elif current_section == 'specifications':
                        if ':' in line:
                            key, value = line.strip('- ').split(':', 1)
                            analysis_dict['specifications'][key.strip()] = value.strip()
                    elif current_section == 'keywords':
                        analysis_dict['search_keywords'].append(line.strip('- '))
                        
            logger.info(f"Parsed analysis: {json.dumps(analysis_dict, indent=2)}")
            return analysis_dict
            
        except Exception as e:
            logger.error(f"Error parsing analysis: {str(e)}")
            return analysis_dict
    
    async def analyze_product(self, image_path):
        try:
            image = Image.open(image_path)
            
            analysis_prompt = [
                """Analyze this product image and provide detailed information in the following format exactly:

BEGIN_ANALYSIS
Product Name: [exact product name]
Category: [main category/subcategory]
Description: [2-3 sentences about the product]
Price: [all visible pricing information]
Key Features:
- [feature 1]
- [feature 2]
- [feature 3]
- [feature 4]
- [feature 5]
Specifications:
- Size: [dimensions if visible]
- Material: [main materials]
- Color: [available colors]
- Weight: [if visible]
Search Keywords:
- [keyword 1]
- [keyword 2]
- [keyword 3]
- [keyword 4]
- [keyword 5]
END_ANALYSIS""",
                image
            ]
            
            response = self.model.generate_content(analysis_prompt)
            analysis_dict = self._parse_analysis(response.text)
            analysis_dict['status'] = 'success'
            
            return analysis_dict
            
        except Exception as e:
            logger.error(f"Error in analyze_product: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
        

class TokenBucket:
    def __init__(self, tokens_per_second=1, max_tokens=60):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(
                self.max_tokens,
                self.tokens + time_passed * self.tokens_per_second
            )
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
    
    async def wait(self):
        while not await self.acquire():
            await asyncio.sleep(1.0 / self.tokens_per_second)

class TextProcessor:
    def __init__(self, api_key):
        load_dotenv()
        self.api_key = api_key
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-pro-latest")
    
    def _parse_analysis(self, text):
        """Parse the analysis text into structured format"""
        analysis_dict = {
            'product_name': '',
            'category': '',
            'description': '',
            'price': '',
            'key_features': [],
            'specifications': {},
            'search_keywords': []
        }
        
        try:
            # Remove BEGIN_ANALYSIS and END_ANALYSIS
            if 'BEGIN_ANALYSIS' in text and 'END_ANALYSIS' in text:
                content = text.split('BEGIN_ANALYSIS')[-1].split('END_ANALYSIS')[0].strip()
            else:
                content = text.strip()
            
            # Split into lines
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('Product Name:'):
                    analysis_dict['product_name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Category:'):
                    analysis_dict['category'] = line.split(':', 1)[1].strip()
                elif line.startswith('Description:'):
                    analysis_dict['description'] = line.split(':', 1)[1].strip()
                elif line.startswith('Price:'):
                    analysis_dict['price'] = line.split(':', 1)[1].strip()
                elif line.startswith('Key Features:'):
                    current_section = 'features'
                elif line.startswith('Specifications:'):
                    current_section = 'specifications'
                elif line.startswith('Search Keywords:'):
                    current_section = 'keywords'
                elif line.startswith('- '):
                    if current_section == 'features':
                        analysis_dict['key_features'].append(line.strip('- '))
                    elif current_section == 'specifications':
                        if ':' in line:
                            key, value = line.strip('- ').split(':', 1)
                            analysis_dict['specifications'][key.strip()] = value.strip()
                    elif current_section == 'keywords':
                        analysis_dict['search_keywords'].append(line.strip('- '))
                        
            logger.info(f"Parsed analysis: {json.dumps(analysis_dict, indent=2)}")
            return analysis_dict
            
        except Exception as e:
            logger.error(f"Error parsing analysis: {str(e)}")
            return analysis_dict
    
    async def analyze_text(self, text):
        try:
            prompt = f"""Analyze this product-related text and provide information in the following format exactly:

BEGIN_ANALYSIS
Product Name: [extract or infer product name]
Category: [main category/subcategory]
Description: [2-3 sentences summarizing the product]
Price: [any mentioned pricing]
Key Features:
- [feature 1]
- [feature 2]
- [feature 3]
- [feature 4]
- [feature 5]
Specifications:
- Size: [any mentioned dimensions]
- Material: [mentioned materials]
- Color: [mentioned colors]
- Weight: [if mentioned]
Search Keywords:
- [keyword 1]
- [keyword 2]
- [keyword 3]
- [keyword 4]
- [keyword 5]
END_ANALYSIS

Text to analyze:
{text}"""
            
            response = self.model.generate_content(prompt)
            analysis_dict = self._parse_analysis(response.text)
            analysis_dict['status'] = 'success'
            
            return analysis_dict
            
        except Exception as e:
            logger.error(f"Error in analyze_text: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }























