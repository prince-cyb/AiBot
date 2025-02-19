import logging
import os
from typing import Optional, cast
import asyncio
from contextlib import suppress
import signal
import threading

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from telegram.error import NetworkError, TimedOut, Forbidden, TelegramError
from telegram.constants import ChatAction

from bot import MayaBot
from config import Config

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Global bot instance and initialization lock
maya_instance = None
init_lock = threading.Lock()

def init_maya_bot():
    """Initialize Maya bot with proper error handling"""
    global maya_instance
    with init_lock:
        if maya_instance is not None:
            return maya_instance

        try:
            logger.info("Initializing Maya bot instance...")
            maya_instance = MayaBot()
            logger.info("Maya bot instance initialized successfully")
            return maya_instance
        except Exception as e:
            logger.error(f"Failed to initialize Maya bot: {str(e)}", exc_info=True)
            raise

async def graceful_shutdown(app: Application):
    """Handle graceful shutdown of the bot"""
    logger.info("Initiating graceful shutdown...")
    try:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Bot shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if not update or not update.message:
        return

    try:
        welcome_message = """
Hello! 👋 I'm Maya, your AI companion. I'm here to chat, support, and get to know you better.

You can:
• Just start chatting with me
• Use /premium to toggle premium features
• Use /help to see all available commands

Let me know how I can assist you today! 😊
        """
        user = update.effective_user
        logger.info(f"Start command received from user {user.id}")

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        await update.message.reply_text(
            f"Hi {user.first_name}! {welcome_message}"
        )
        logger.info(f"Welcome message sent to user {user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "Sorry, I'm having trouble right now. Please try again later."
            )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    if not update or not update.message:
        return

    try:
        help_text = """
Available commands:
/start - Start conversation with Maya
/help - Show this help message
/premium - Toggle premium features
/stats - View your chat statistics

Tips:
• You can ask me anything!
• I learn from our conversations
• Premium users get longer responses
• I'm always here to chat and support you
        """
        logger.info(f"Help command received from user {update.effective_user.id}")

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        await update.message.reply_text(help_text)
        logger.info(f"Help message sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "Sorry, I couldn't display the help message. Please try again."
            )

async def toggle_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle premium status."""
    if not update or not update.message:
        return

    try:
        user_id = update.effective_user.id
        logger.info(f"Premium toggle requested by user {user_id}")

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        if maya_instance:
            response = maya_instance.toggle_premium(telegram_id=user_id)
            await update.message.reply_text(response)
            logger.info(f"Premium status toggled for user {user_id}")
        else:
            logger.error("Maya instance not initialized")
            await update.message.reply_text(
                "Sorry, the bot is not properly initialized. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error toggling premium: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "Sorry, I couldn't update your premium status. Please try again later."
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the user message and respond using Maya."""
    if not update or not update.message or not update.message.text or not maya_instance:
        return

    try:
        user_text = update.message.text.strip()
        user_id = update.effective_user.id
        logger.info(f"Received message from user {user_id}: {user_text[:50]}...")

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        logger.debug("Calling Maya bot to handle message")
        response = maya_instance.handle_message(user_text, telegram_id=user_id)

        if response and update.message:
            logger.debug(f"Sending response to user {user_id}: {response[:50]}...")
            await update.message.reply_text(response)
            logger.info(f"Successfully sent response to user {user_id}")
        else:
            logger.warning(f"No response generated for user {user_id}")
            await update.message.reply_text(
                "I apologize, but I couldn't generate a response. Please try again."
            )

    except (NetworkError, TimedOut) as e:
        logger.error(f"Network error: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "I'm having connection issues. Please try again in a moment."
            )
    except Forbidden as e:
        logger.error(f"Bot was blocked by user: {str(e)}", exc_info=True)
    except TelegramError as e:
        logger.error(f"Telegram error: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "I'm having trouble with the Telegram service. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "I'm having trouble processing your message. Please try again."
            )

async def error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=True)
    try:
        if update and update.message:
            await update.message.reply_text(
                "An error occurred while processing your request. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}", exc_info=True)

async def run_telegram_bot():
    """Start the Telegram bot."""
    app = None
    try:
        # Validate Telegram token
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            logger.error("TELEGRAM_TOKEN not found in environment variables")
            raise ValueError("TELEGRAM_TOKEN environment variable must be set")

        # Initialize Maya bot first to ensure AI services are ready
        try:
            logger.info("Starting Maya bot initialization...")
            maya_instance = init_maya_bot()
            if not maya_instance:
                raise RuntimeError("Maya bot initialization failed")
            logger.info("Maya bot initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Maya bot: {str(e)}", exc_info=True)
            raise

        # Build application with timeout settings
        logger.info("Building Telegram application...")
        app = Application.builder().token(token).connect_timeout(30).read_timeout(30).write_timeout(30).build()

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("premium", toggle_premium))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)

        # Initialize and start the application with proper sequence
        logger.info("Starting bot polling...")
        await app.initialize()
        await app.start()
        logger.info("Bot application started successfully")

        # Configure and start the updater with explicit timeouts
        logger.info("Configuring updater...")
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30
        )
        logger.info("Bot is now polling for updates")

        # Wait for updates indefinitely
        logger.info("Waiting for updates...")
        try:
            await asyncio.Event().wait()  # Wait indefinitely
        except Exception as e:
            logger.warning(f"Update polling stopped: {str(e)}")

    except NetworkError as e:
        logger.error(f"Network error during bot startup: {str(e)}", exc_info=True)
        raise
    except TimedOut as e:
        logger.error(f"Connection timed out during bot startup: {str(e)}", exc_info=True)
        raise
    except TelegramError as e:
        logger.error(f"Telegram API error during bot startup: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Critical error starting bot: {str(e)}", exc_info=True)
        if app:
            try:
                await graceful_shutdown(app)
            except Exception as shutdown_error:
                logger.error(f"Error during shutdown: {str(shutdown_error)}", exc_info=True)
        raise
    finally:
        if app:
            try:
                await graceful_shutdown(app)
            except Exception as shutdown_error:
                logger.error(f"Error during final shutdown: {str(shutdown_error)}", exc_info=True)

def main():
    """Entry point for running the bot"""
    try:
        # Set up the event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        logger.info("Starting Telegram bot with event loop...")
        loop.run_until_complete(run_telegram_bot())

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        raise
    finally:
        loop.close()

if __name__ == '__main__':
    main()