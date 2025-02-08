from config import *
from database import DatabaseManager
from api_client import APIClient
import logging
import asyncio
from datetime import datetime
import pytz

# Configure logging once at the top level
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
db_manager = DatabaseManager(DB_FILE)

# The rest of your command handlers would go here, but modified to use the new classes