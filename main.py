import logging
import signal
import sys
import asyncio
from telegram_bot import run_telegram_bot
from bot import MayaBot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

maya_bot = None
shutdown_event = asyncio.Event()

def cleanup():
    """Cleanup resources before shutdown"""
    global maya_bot
    if maya_bot:
        logger.info("Cleaning up bot resources...")
        try:
            maya_bot.cleanup()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()

async def main():
    """Main async entry point"""
    try:
        logger.info("Starting Maya bot application...")
        # Run the bot using asyncio
        await run_telegram_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        logger.info("Starting event loop...")
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application stopped due to error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            loop.close()
            logger.info("Event loop closed")
        except Exception as e:
            logger.error(f"Error closing event loop: {str(e)}", exc_info=True)