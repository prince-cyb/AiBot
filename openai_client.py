import logging
from openai import OpenAI
from typing import Optional
import os

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        logger.debug("Initializing OpenAIClient...")
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY must be set in environment variables")

        try:
            logger.debug("Creating OpenAI client...")
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAIClient initialized successfully")
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {str(e)}", exc_info=True)
            raise

    def get_response(self, message: str, persona: str, max_tokens: int = 150) -> Optional[str]:
        """
        Get AI response from OpenAI API
        """
        try:
            logger.debug(f"Preparing OpenAI API request for message length: {len(message)}")
            logger.debug(f"Using max_tokens: {max_tokens}")

            logger.debug("Creating chat completion request...")
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using gpt-3.5-turbo for reliability
                messages=[
                    {"role": "system", "content": persona},
                    {"role": "user", "content": message}
                ],
                max_tokens=max_tokens,
                temperature=0.7,
                presence_penalty=0.6,  # Encourage varied responses
                frequency_penalty=0.0
            )
            logger.debug("Chat completion request sent successfully")

            if response and response.choices:
                answer = response.choices[0].message.content
                logger.info("Successfully received response from OpenAI API")
                logger.debug(f"Response length: {len(answer)} characters")
                return answer

            logger.error("Received empty response from OpenAI API")
            logger.debug(f"Raw API response: {response}")
            return None

        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}", exc_info=True)
            return None