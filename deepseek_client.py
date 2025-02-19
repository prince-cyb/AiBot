import os
import requests
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)

class DeepseekClient:
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            logger.error("DEEPSEEK_API_KEY not found in environment variables")
            raise ValueError("DEEPSEEK_API_KEY must be set in environment variables")

        # Updated base URL to the correct endpoint
        self.base_url = "https://api.deepseek.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        logger.info("DeepseekClient initialized successfully")

    def get_response(self, message: str, persona: str, max_retries: int = 3, max_tokens: int = 150) -> Optional[str]:
        """
        Get AI response from Deepseek API with retry logic
        """
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.debug(f"Attempting API call (attempt {retry_count + 1}/{max_retries})")

                payload = {
                    "model": "deepseek-chat-v1",
                    "messages": [
                        {"role": "system", "content": persona},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                    "top_p": 0.9
                }

                logger.debug(f"Sending request to Deepseek API with payload: {payload}")
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data["choices"][0]["message"]["content"]
                    logger.info("Successfully received response from Deepseek API")
                    return answer

                elif response.status_code == 401:
                    logger.error("Authentication failed. Please check your API key.")
                    return "I'm having trouble authenticating with my AI service. Please contact support."

                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limit hit. Waiting {retry_after} seconds before retry.")
                    time.sleep(retry_after)
                    retry_count += 1
                    continue

                else:
                    logger.error(f"API Error: {response.status_code} - {response.text}")
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue

            except requests.exceptions.Timeout:
                logger.error("Request timed out")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)
                    continue
                return "The request took too long. Please try again."

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)
                    continue
                return "There was a problem connecting to the AI service. Please try again later."

            except Exception as e:
                logger.error(f"Unexpected error in Deepseek API call: {str(e)}")
                return "I'm having trouble processing that right now. Could you try again?"

        logger.error(f"Failed to get response after {max_retries} retries")
        return "I'm having persistent issues connecting to my AI service. Please try again later."