"""
Database initialization script
Run this script to initialize the database with sample data
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone
from src.backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def init_database():
    """Initialize database with sample data"""
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    
    try:
        # Test connection
        await client.admin.command('ping')
        print(f"✓ Connected to MongoDB database: {settings.MONGODB_DB_NAME}")
        
        # Create indexes
        print("\nCreating indexes...")
        
        # Users collection indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("created_at")
        print("✓ Users indexes created")
        
        # Content collection indexes
        await db.content.create_index("user_id")
        await db.content.create_index("created_at")
        await db.content.create_index([("user_id", 1), ("created_at", -1)])
        print("✓ Content indexes created")
        
        # Questions collection indexes
        await db.questions.create_index("content_id")
        await db.questions.create_index("user_id")
        await db.questions.create_index("created_at")
        await db.questions.create_index([("content_id", 1), ("created_at", -1)])
        await db.questions.create_index([("user_id", 1), ("created_at", -1)])
        print("✓ Questions indexes created")
        
        # Analytics collection indexes
        await db.analytics.create_index("user_id")
        await db.analytics.create_index("content_id")
        await db.analytics.create_index("event_type")
        await db.analytics.create_index("timestamp")
        await db.analytics.create_index([("user_id", 1), ("timestamp", -1)])
        print("✓ Analytics indexes created")
        
        # Create sample users
        print("\nCreating sample users...")
        
        sample_users = [
            {
                "email": "student@example.com",
                "name": "John Doe",
                "role": "student",
                "hashed_password": pwd_context.hash("password123"),
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "total_contents": 0,
                "total_questions": 0
            },
            {
                "email": "teacher@example.com",
                "name": "Jane Smith",
                "role": "teacher",
                "hashed_password": pwd_context.hash("password123"),
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "total_contents": 0,
                "total_questions": 0
            }
        ]
        
        for user_data in sample_users:
            # Check if user exists
            existing_user = await db.users.find_one({"email": user_data["email"]})
            if not existing_user:
                await db.users.insert_one(user_data)
                print(f"✓ Created user: {user_data['email']}")
            else:
                print(f"- User already exists: {user_data['email']}")
        
        print("\n✅ Database initialization completed successfully!")
        print("\nSample login credentials:")
        print("  Student: student@example.com / password123")
        print("  Teacher: teacher@example.com / password123")
        
    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(init_database())

