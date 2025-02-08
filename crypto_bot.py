import logging
import requests
import sqlite3
import asyncio
import os
import sys
from datetime import datetime
import pytz
from typing import Dict, Optional
import time
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackContext
)
from pycoingecko import CoinGeckoAPI

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,  # Changed from DEBUG to INFO for production
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# API Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', "7805898799:TELEGRAM_TOKEN")
CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY', "CRYPTOPANIC_API_KEY")
CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/v1/posts/"

# Constants
CACHE_FILE = "coins_cache.json"
CACHE_DURATION = 3600  # 1 hour
PER_PAGE = 250
MAX_SUBSCRIPTIONS = 10
NEWS_CHECK_INTERVAL = 600  # 10 minutes
DB_FILE = "crypto_bot.db"

# Initialize CoinGecko API client
cg = CoinGeckoAPI()

# Conversation states
ASKING_FOR_TOKEN = 1

class CoinGeckoManager:
    def __init__(self):
        self.cg = CoinGeckoAPI()
        self.last_update = 0
        self.coins_data = {}
        
    async def _fetch_coins_page(self, page: int) -> list:
        """Fetch a single page of coins from CoinGecko API with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1.5)  # Rate limiting
                return self.cg.get_coins_markets(
                    vs_currency='usd',
                    order='market_cap_desc',
                    per_page=PER_PAGE,
                    page=page,
                    sparkline=False
                )
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Retry {attempt + 1} after error: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
    def _load_cache(self) -> bool:
        """Load cached coin data if available and recent."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                    if time.time() - cache_data['timestamp'] < CACHE_DURATION:
                        self.coins_data = cache_data['coins']
                        self.last_update = cache_data['timestamp']
                        return True
        except Exception as e:
            logger.error(f"Cache loading error: {e}")
        return False

    def _save_cache(self):
        """Save coin data to cache file with error handling."""
        try:
            cache_data = {
                'timestamp': time.time(),
                'coins': self.coins_data
            }
            # Write to temporary file first
            temp_file = f"{CACHE_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(cache_data, f)
            # Atomic rename
            os.replace(temp_file, CACHE_FILE)
        except Exception as e:
            logger.error(f"Cache saving error: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    async def get_all_coins(self, force_update: bool = False) -> Dict:
        """Fetch all coins from CoinGecko API with improved error handling."""
        if not force_update and self._load_cache():
            return self.coins_data

        coins = {}
        page = 1
        
        try:
            while True:
                response = await self._fetch_coins_page(page)
                
                if not response:
                    break

                for coin in response:
                    coins[coin['symbol'].lower()] = {
                        'id': coin['id'],
                        'symbol': coin['symbol'].lower(),
                        'name': coin['name'],
                        'market_cap_rank': coin.get('market_cap_rank'),
                        'market_cap': coin.get('market_cap'),
                        'current_price': coin.get('current_price'),
                        'last_updated': coin.get('last_updated')
                    }

                if len(response) < PER_PAGE:
                    break
                page += 1

            self.coins_data = coins
            self.last_update = time.time()
            self._save_cache()
            return coins

        except Exception as e:
            logger.error(f"Error fetching coins: {e}")
            # Return cached data if available, otherwise raise
            if self.coins_data:
                logger.info("Returning cached data after fetch error")
                return self.coins_data
            raise

async def init_database():
    """Initialize the SQLite database with proper error handling."""
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id TEXT,
                    token TEXT,
                    user_name TEXT,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_update TIMESTAMP,
                    login TEXT,
                    PRIMARY KEY (chat_id, token)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id TEXT,
                    login TEXT,
                    action TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            """)
            await db.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

async def log_user_activity(user_id: str, login: str, action: str, details: str = ""):
    """Log user activity to database with async support."""
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                INSERT INTO user_activity (user_id, login, action, details)
                VALUES (?, ?, ?, ?)
            """, (user_id, login, action, details))
            await db.commit()
    except Exception as e:
        logger.error(f"Error logging user activity: {e}")

# ... [Previous command handlers remain the same] ...

async def main():
    """Initialize and run the bot with improved error handling."""
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized")
        
        # Create application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        handlers = [
            CommandHandler("start", start),
            CommandHandler("help", help_command),
            CommandHandler("crypto_news", crypto_news),
            CommandHandler("coins", list_coins),
            CommandHandler("mysubs", my_subscriptions),
            CommandHandler("unsubscribe", unsubscribe),
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        # Add conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("subscribe", start_subscription)],
            states={
                ASKING_FOR_TOKEN: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        handle_subscription
                    )
                ]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
        )
        application.add_handler(conv_handler)
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Set up periodic tasks
        application.job_queue.run_repeating(
            check_news_updates,
            interval=NEWS_CHECK_INTERVAL,
            first=10
        )
        application.job_queue.run_repeating(
            update_coin_list,
            interval=CACHE_DURATION,
            first=5
        )
        
        logger.info("Starting bot...")
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        raise
    finally:
        # Ensure proper cleanup
        if 'application' in locals():
            await application.stop()

if __name__ == "__main__":
    try:
        # Print startup information
        current_time = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Starting bot at {current_time}")
        
        # Run the async main function
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
