import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def inspect():
    mongo_url = os.getenv("MONGO_URL")
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_database()
    
    user = await db.users.find_one()
    print(f"Sample User Document: {user}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(inspect())
