import asyncio
import logging
import os
from bot.bot import AutoRecordBot
from config.config import DISCORD_TOKEN, LOGS_DIR

# Set up logging configuration
def setup_logging():
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log')),
            logging.StreamHandler()  # Also print to console
        ]
    )

async def main():
    try:
        # Set up logging first
        setup_logging()
        logging.info("Starting Nouncil Auto Recording Bot...")
        
        # Initialize and start the bot
        bot = AutoRecordBot()
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise  # Re-raise the exception after logging
    finally:
        logging.info("Bot shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")