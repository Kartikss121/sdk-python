import asyncio
import os
from runware import Runware, IModelSearch
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("RUNWARE_API_KEY")
    if not api_key:
        print("RUNWARE_API_KEY not found in .env")
        return
        
    runware = Runware(api_key=api_key)
    await runware.connect()
    
    print("Searching for 'flux klein' models...")
    search_results = await runware.modelSearch(
        payload=IModelSearch(search="flux 2")
    )
    
    for model in search_results.results:
        print(f"Name: {model.name}")
        print(f"AIR: {model.air}")
        print("-" * 20)
        
    await runware.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
