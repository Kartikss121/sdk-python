import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check_credits():
    mongo_url = os.getenv("MONGO_URL")
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_database()
    
    # Get all users to see their credits
    users = await db.users.find().to_list(length=10)
    print("--- User Credits in DB ---")
    for user in users:
        print(f"User ID: {user.get('user_id')} | Email: {user.get('email')} | Credits: {user.get('credits')}")
    print("--------------------------")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_credits())
