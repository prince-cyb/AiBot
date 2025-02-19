from datetime import datetime
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from ratelimit import limits, sleep_and_retry
from models import User, Message, BotPersonality, Session, Base, engine
from gemini_client import GeminiClient
from config import Config
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import event, text
from sqlalchemy.pool import Pool

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Add connection pool event listeners
@event.listens_for(Pool, "checkout")
def check_connection(dbapi_connection, connection_record, connection_proxy):
    """Verify database connection is still alive"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        logger.debug("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection verification failed: {str(e)}", exc_info=True)
        raise

class MayaBot:
    def __init__(self):
        """Initialize the bot with proper error handling and verification"""
        logger.info("Initializing MayaBot...")
        try:
            # Ensure database and tables are created
            Base.metadata.create_all(engine)
            logger.info("Database tables verified")

            # Initialize AI client
            logger.info("Initializing Gemini client...")
            self.ai_client = GeminiClient()
            logger.info("Successfully initialized GeminiClient")

            # Initialize session and user
            self.setup_user()
            self.ensure_default_personality()
            logger.info("Bot initialization completed successfully")

        except Exception as e:
            logger.exception(f"Critical error during bot initialization: {str(e)}") #Improved logging
            raise

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations with retries."""
        session = Session()
        try:
            yield session
            session.commit()
        except OperationalError as e:
            logger.exception(f"Database operational error: {str(e)}") #Improved logging
            session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.exception(f"Database error: {str(e)}") #Improved logging
            session.rollback()
            raise
        finally:
            session.close()

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_user(self, session, telegram_id: Optional[int] = None) -> Optional[User]:
        """Get or create user with proper session binding and retries"""
        try:
            query = session.query(User)
            if telegram_id:
                user = query.filter(User.telegram_id == telegram_id).first()
            else:
                user = query.first()

            if not user and telegram_id:
                logger.info(f"Creating new user with telegram_id: {telegram_id}")
                user = User(
                    name="User",
                    telegram_id=telegram_id,
                    created_at=datetime.utcnow(),
                    is_premium=False
                )
                session.add(user)
                session.commit()
            return user
        except Exception as e:
            logger.exception(f"Error in get_user: {str(e)}") #Improved logging
            raise

    def setup_user(self):
        """Initialize default user with retries"""
        try:
            with self.session_scope() as session:
                user = self.get_user(session)
                if user:
                    self.user_id = user.id
                    logger.info(f"User setup completed. ID: {self.user_id}")
                else:
                    logger.warning("No default user found")
        except Exception as e:
            logger.exception(f"Error in setup_user: {str(e)}") #Improved logging
            raise

    def ensure_default_personality(self):
        """Ensure there's at least one personality configured with retry logic"""
        try:
            with self.session_scope() as session:
                personality = session.query(BotPersonality).filter_by(is_active=True).first()
                if not personality:
                    logger.info("Creating default personality")
                    default_personality = BotPersonality(
                        persona=Config.DEFAULT_PERSONA,
                        name="Default",
                        description="Default caring and empathetic personality",
                        is_active=True
                    )
                    session.add(default_personality)
                    session.commit()
                    logger.info("Default personality created successfully")
        except Exception as e:
            logger.exception(f"Error ensuring default personality: {str(e)}") #Improved logging
            raise

    @sleep_and_retry
    @limits(calls=Config.RATE_LIMIT_CALLS, period=Config.RATE_LIMIT_PERIOD)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def handle_message(self, text: str, telegram_id: Optional[int] = None) -> str:
        """Process user message and return AI response with rate limiting and retry logic"""
        if not text:
            logger.warning("Received empty message")
            return "I couldn't understand your message. Could you please try again?"

        try:
            logger.info(f"Processing message from telegram_id {telegram_id}: {text[:50]}...")
            
            with self.session_scope() as session:
                user = self.get_user(session, telegram_id)
                if not user:
                    return "There was an error with your session. Please try again."
                
                # Get recent message history for context
                recent_messages = (
                    session.query(Message)
                    .filter(Message.user_id == user.id)
                    .order_by(Message.timestamp.desc())
                    .limit(5)
                    .all()
                )
                
                # Build context from recent messages
                context = ""
                for msg in reversed(recent_messages):
                    prefix = "Maya: " if msg.is_from_bot else "User: "
                    context += f"{prefix}{msg.content}\n"
                context += f"User: {text}\n"

            with self.session_scope() as session:
                # Get or create user
                user = self.get_user(session, telegram_id)
                if not user:
                    logger.error(f"User not found/created for telegram_id: {telegram_id}")
                    return "There was an error with your session. Please try again."

                # Update last interaction
                user.last_interaction = datetime.utcnow()

                # Save user message
                message = Message(
                    user_id=user.id,
                    content=text,
                    is_from_bot=False,
                    telegram_message_id=None
                )
                session.add(message)
                logger.debug("User message saved")

                # Get active personality
                personality = session.query(BotPersonality).filter_by(is_active=True).first()
                if not personality:
                    logger.error("No active personality found")
                    return "I'm having trouble with my personality configuration. Please contact support."

                # Get AI response with context
                logger.info("Requesting AI response with context...")
                max_tokens = Config.PREMIUM_MAX_TOKENS if user.is_premium else Config.DEFAULT_MAX_TOKENS
                full_prompt = f"{personality.persona}\n\nConversation history:\n{context}\nMaya:"
                response = self.ai_client.get_response(full_prompt, personality.persona, max_tokens=max_tokens)

                if response:
                    # Add creator info to all responses
                    creator_info = "\n\nI was created by @Lonely_Shark on Telegram. You can also find my creator on Instagram: https://www.instagram.com/who.s_prince?igsh=d3NoZWM0a3Fwdjkz"
                    full_response = response + creator_info
                    
                    # Save bot response
                    bot_message = Message(
                        user_id=user.id,
                        content=full_response,
                        is_from_bot=True,
                        telegram_message_id=None
                    )
                    session.add(bot_message)
                    logger.info(f"AI response saved: {response[:50]}...")
                    return response
                else:
                    logger.error("Received empty response from AI service")
                    return "I apologize, but I couldn't generate a response. Please try again."

        except Exception as e:
            logger.exception(f"Error in handle_message: {str(e)}") #Improved logging
            return "I'm having trouble processing that right now. Could you try again?"

    def toggle_premium(self, telegram_id: Optional[int] = None) -> str:
        """Toggle premium status for the user"""
        try:
            with self.session_scope() as session:
                user = self.get_user(session, telegram_id)
                if user:
                    user.is_premium = not user.is_premium
                    status = "enabled" if user.is_premium else "disabled"
                    logger.info(f"Premium status {status} for user {user.id}")
                    return f"Premium features {status}"
                return "Error: User not found"
        except Exception as e:
            logger.exception(f"Error in toggle_premium: {str(e)}") #Improved logging
            return "Error toggling premium status"

    def run(self):
        """Start the chat loop for local testing"""
        print("Hello! I'm Maya, your AI companion. 👋")
        print("I'm here to chat, support, and get to know you better.")
        print("Type 'exit' to end the chat, or 'premium' to toggle premium features.")
        print("Feel free to tell me about your day or ask me anything!")

        while True:
            try:
                user_input = input("\nYou: ").strip()

                if user_input.lower() == 'exit':
                    print("\nGoodbye! Take care! 👋")
                    break
                elif user_input.lower() == 'premium':
                    print("\nMaya:", self.toggle_premium())
                    continue

                response = self.handle_message(user_input)
                # Check if user is asking about identity or creator
                if any(q in user_input.lower() for q in ["who are you", "who made you", "your creator"]):
                    response = f"{response}\n\nI was created by @Lonely_Shark on Telegram. You can also find my creator on Instagram: https://www.instagram.com/who.s_prince?igsh=d3NoZWM0a3Fwdjkz"
                print("\nMaya:", response)

            except KeyboardInterrupt:
                print("\nGoodbye! Take care! 👋")
                break
            except Exception as e:
                logger.exception(f"Error in run loop: {str(e)}") #Improved logging
                print("\nI'm having trouble processing that. Could you try again?")
    
    def cleanup(self):
        """Cleanup resources used by the bot"""
        try:
            logger.info("Starting bot cleanup...")
            with self.session_scope() as session:
                # Commit any pending transactions
                session.commit()
                logger.debug("Database session committed")
            logger.info("Bot cleanup completed successfully")
        except Exception as e:
            logger.exception(f"Error during bot cleanup: {str(e)}") #Improved logging
            raise