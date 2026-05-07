import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from runware import Runware
from dotenv import load_dotenv

load_dotenv()

async def diagnose():
    print("--- Diagnostics Started ---")
    
    # 1. Check Runware
    api_key = os.getenv("RUNWARE_API_KEY")
    print(f"Runware API Key present: {bool(api_key)}")
    if api_key:
        try:
            runware = Runware(api_key=api_key)
            await runware.connect()
            print("✅ Runware connection successful")
            await runware.disconnect()
        except Exception as e:
            print(f"❌ Runware connection failed: {e}")

    # 2. Check MongoDB
    mongo_url = os.getenv("MONGO_URL")
    print(f"MongoDB URL present: {bool(mongo_url)}")
    if mongo_url:
        try:
            client = AsyncIOMotorClient(mongo_url)
            # Try to ping the database
            await client.admin.command('ping')
            print("✅ MongoDB connection successful")
            
            db = client.get_database()
            print(f"Using database: {db.name}")
            
            # Check collections
            collections = await db.list_collection_names()
            print(f"Collections found: {collections}")
            
            client.close()
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")

    # 3. Check Clerk Key
    clerk_key = os.getenv("CLERK_JWT_PUBLIC_KEY")
    print(f"Clerk Public Key present: {bool(clerk_key)}")
    if clerk_key:
        if "BEGIN PUBLIC KEY" in clerk_key and "END PUBLIC KEY" in clerk_key:
            print("✅ Clerk Public Key format looks valid (PEM)")
        else:
            print("❌ Clerk Public Key format invalid (missing PEM headers)")

    print("--- Diagnostics Finished ---")

if __name__ == "__main__":
    asyncio.run(diagnose())
