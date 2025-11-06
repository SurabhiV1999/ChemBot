from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        try:
            logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
            cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
            cls.db = cls.client[settings.MONGODB_DB_NAME]
            
            # Test connection
            await cls.client.admin.command('ping')
            logger.info(f"Connected to MongoDB database: {settings.MONGODB_DB_NAME}")
            
            # Create indexes
            await cls.create_indexes()
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client is not None:
            cls.client.close()
            logger.info("Closed MongoDB connection")
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes for optimal performance"""
        if cls.db is None:
            return
        
        try:
            # Users collection indexes
            await cls.db.users.create_index("email", unique=True)
            await cls.db.users.create_index("created_at")
            
            # Content collection indexes
            await cls.db.content.create_index("user_id")
            await cls.db.content.create_index("created_at")
            await cls.db.content.create_index([("user_id", 1), ("created_at", -1)])
            
            # Questions collection indexes
            await cls.db.questions.create_index("content_id")
            await cls.db.questions.create_index("user_id")
            await cls.db.questions.create_index("created_at")
            await cls.db.questions.create_index([("content_id", 1), ("created_at", -1)])
            await cls.db.questions.create_index([("user_id", 1), ("created_at", -1)])
            
            # Analytics collection indexes
            await cls.db.analytics.create_index("user_id")
            await cls.db.analytics.create_index("content_id")
            await cls.db.analytics.create_index("event_type")
            await cls.db.analytics.create_index("timestamp")
            await cls.db.analytics.create_index([("user_id", 1), ("timestamp", -1)])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls.db is None:
            raise Exception("Database not initialized")
        return cls.db


# Dependency for FastAPI
async def get_database() -> AsyncIOMotorDatabase:
    """Dependency to get database instance in route handlers"""
    return Database.get_db()

