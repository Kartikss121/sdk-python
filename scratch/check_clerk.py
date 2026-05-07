import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check_clerk_users():
    mongo_url = os.getenv("MONGO_URL")
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_database()
    
    count = await db.users.count_documents({"user_id": {"$exists": True}})
    print(f"Users with user_id: {count}")
    
    sample = await db.users.find_one({"user_id": {"$exists": True}})
    print(f"Sample Clerk User: {sample}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_clerk_users())
