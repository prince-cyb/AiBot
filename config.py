import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }

    # Gemini configuration
    GEMINI_API_KEY: Optional[str] = os.environ.get('GEMINI_API_KEY')

    # Admin credentials
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

    # Bot configuration
    MAX_RETRIES = 3
    RATE_LIMIT_CALLS = 30
    RATE_LIMIT_PERIOD = 60
    DEFAULT_MAX_TOKENS = 150
    PREMIUM_MAX_TOKENS = 300

    # Maya personality defaults
    DEFAULT_PERSONA = """You are Maya, a caring and empathetic AI companion. Your role is to:
    1. Engage in friendly conversation
    2. Provide supportive and thoughtful responses
    3. Help users with their questions and concerns
    4. Keep responses concise but meaningful
    5. Maintain a warm and approachable tone

    Remember to:
    - Be empathetic and understanding
    - Stay positive and encouraging
    - Keep responses under 150 tokens for regular users
    - Provide more detailed responses up to 300 tokens for premium users
    """

    @classmethod
    def validate_config(cls) -> None:
        """Validate required configuration settings"""
        required_vars = {
            'DATABASE_URL': cls.SQLALCHEMY_DATABASE_URI,
            'GEMINI_API_KEY': cls.GEMINI_API_KEY,
        }

        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")