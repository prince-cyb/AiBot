import os
import logging
import threading
import time
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from ratelimit import limits, sleep_and_retry
import google.generativeai as genai
from google.api_core import retry as google_retry
from config import Config

logger = logging.getLogger(__name__)

class InitializationTimeout(Exception):
    """Raised when initialization takes too long"""
    pass

class GeminiClient:
    def __init__(self):
        """Initialize the GeminiClient with robust error handling and logging"""
        logger.info("Starting GeminiClient initialization...")
        self.api_key = Config.GEMINI_API_KEY
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY must be set in environment variables")

        self.initialized = threading.Event()
        self.init_error = None

        try:
            logger.debug("Starting initialization with timeout...")
            self._initialize_with_timeout()
            logger.info("GeminiClient initialization completed successfully")
        except Exception as e:
            logger.exception("Critical error during Gemini API initialization")
            raise

    def _initialize_with_timeout(self, timeout=30):
        """Initialize with timeout to prevent hanging"""
        try:
            logger.debug("Creating initialization thread...")
            init_thread = threading.Thread(target=self._safe_initialize)
            init_thread.start()
            logger.debug("Waiting for initialization to complete...")

            if not self.initialized.wait(timeout):
                logger.error("Initialization timed out after %d seconds", timeout)
                raise InitializationTimeout("Gemini API initialization timed out")

            if self.init_error:
                logger.error("Initialization failed with error", exc_info=self.init_error)
                raise self.init_error

            logger.debug("Initialization completed successfully")
        except Exception as e:
            logger.exception("Error in initialization with timeout")
            raise

    def _safe_initialize(self):
        """Safely initialize the API with error handling"""
        try:
            logger.debug("Beginning safe initialization...")
            self._initialize_with_retry()
            logger.debug("Safe initialization completed successfully")
            self.initialized.set()
        except Exception as e:
            logger.exception("Error during safe initialization")
            self.init_error = e
            self.initialized.set()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _initialize_with_retry(self):
        """Initialize the Gemini API with retry logic"""
        try:
            logger.debug("Configuring Gemini API with provided key...")
            genai.configure(api_key=self.api_key)

            logger.debug("Creating GenerativeModel instance...")
            self.model = genai.GenerativeModel('gemini-pro')

            # Test the API connection with a simple query
            logger.info("Testing API connection...")
            test_response = self.model.generate_content(
                "Test connection",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=10
                )
            )

            if test_response and hasattr(test_response, 'text') and test_response.text:
                logger.info("Successfully tested Gemini API connection")
            else:
                logger.error("Failed to verify Gemini API connection - empty response")
                raise ConnectionError("Could not verify Gemini API connection")
        except Exception as e:
            logger.exception("Error during API initialization")
            raise

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @sleep_and_retry
    @limits(calls=Config.RATE_LIMIT_CALLS, period=Config.RATE_LIMIT_PERIOD)
    @google_retry.Retry(predicate=google_retry.if_exception_type(Exception))
    def get_response(self, message: str, persona: str, max_tokens: int = Config.DEFAULT_MAX_TOKENS) -> Optional[str]:
        """Get AI response from Gemini API with comprehensive error handling"""
        if not message:
            logger.warning("Empty message received")
            return None

        if not self.initialized.is_set():
            logger.error("Attempting to use uninitialized client")
            return "I'm still initializing. Please try again in a moment."

        try:
            logger.debug(f"Preparing Gemini API request for message: {message[:50]}...")
            logger.debug(f"Using max_tokens: {max_tokens}")

            # Combine persona and message into prompt
            prompt = f"{persona}\n\nUser: {message}\nAssistant:"
            logger.debug(f"Combined prompt length: {len(prompt)}")

            logger.debug("Creating content generation request...")
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=max_tokens,
                    top_p=0.9,
                    top_k=40,
                )
            )
            logger.debug("Content generation request completed")

            if response and hasattr(response, 'text') and response.text:
                answer = response.text.strip()
                logger.info("Successfully received response from Gemini API")
                logger.debug(f"Response length: {len(answer)} characters")
                return answer

            logger.error("Received invalid response from Gemini API")
            return None

        except Exception as e:
            error_msg = str(e).lower()
            logger.exception(f"Error in Gemini API call: {str(e)}")

            if "quota exceeded" in error_msg:
                return "I apologize, but I've reached my usage limit. Please try again later."
            elif "rate limit" in error_msg:
                return "I'm receiving too many requests right now. Please try again in a moment."
            elif "permission" in error_msg or "unauthorized" in error_msg:
                return "I'm having trouble accessing my AI capabilities. Please contact support."
            elif "invalid" in error_msg:
                return "I'm having trouble understanding the request. Please try rephrasing it."
            elif "timeout" in error_msg:
                raise TimeoutError("Request to Gemini API timed out")
            elif "connect" in error_msg:
                raise ConnectionError("Failed to connect to Gemini API")

            return "I encountered an unexpected error. Please try again later."