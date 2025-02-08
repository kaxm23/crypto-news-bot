import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')
CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/v1/posts/"

# Constants
CACHE_FILE = "coins_cache.json"
CACHE_DURATION = 3600  # 1 hour
PER_PAGE = 250  # Maximum allowed by CoinGecko
MAX_SUBSCRIPTIONS = 10
NEWS_CHECK_INTERVAL = 600  # 10 minutes
DB_FILE = "crypto_bot.db"