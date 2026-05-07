import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def find_clerk_user():
    mongo_url = os.getenv("MONGO_URL")
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_database()
    
    # Find any user that has a non-null user_id
    clerk_users = await db.users.find({"user_id": {"$exists": True, "$ne": None}}).to_list(length=5)
    print(f"Found {len(clerk_users)} Clerk users.")
    for u in clerk_users:
        print(f"User: {u.get('email')} | Credits: {u.get('credits')} | ID: {u.get('user_id')}")
    
    # Also check the 'usage' collection
    usage = await db.usage.find().to_list(length=5)
    print(f"\nFound {len(usage)} usage records.")
    for res in usage:
        print(f"Usage: {res}")

    client.close()

if __name__ == "__main__":
    asyncio.run(find_clerk_user())
