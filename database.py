import aiosqlite
from datetime import datetime
import pytz
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file

    async def init_database(self):
        """Initialize the SQLite database."""
        async with aiosqlite.connect(self.db_file) as db:
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

    async def log_activity(self, user_id: str, login: str, action: str, details: str = ""):
        """Log user activity to database."""
        try:
            async with aiosqlite.connect(self.db_file) as db:
                await db.execute("""
                    INSERT INTO user_activity (user_id, login, action, details)
                    VALUES (?, ?, ?, ?)
                """, (user_id, login, action, details))
                await db.commit()
        except Exception as e:
            logger.error(f"Error logging user activity: {e}")

    async def get_subscriptions(self, chat_id: Optional[str] = None) -> List[Tuple]:
        """Get all subscriptions or subscriptions for a specific chat_id."""
        async with aiosqlite.connect(self.db_file) as db:
            if chat_id:
                cursor = await db.execute("""
                    SELECT token, subscribed_at, last_update
                    FROM subscriptions 
                    WHERE chat_id = ? 
                    ORDER BY subscribed_at DESC
                """, (chat_id,))
            else:
                cursor = await db.execute("""
                    SELECT DISTINCT chat_id, token, user_name, login
                    FROM subscriptions
                """)
            return await cursor.fetchall()