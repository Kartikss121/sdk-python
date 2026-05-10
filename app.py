import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from runware import Runware, IImageInference, IVideoInference
from dotenv import load_dotenv
from jose import jwt
from motor.motor_asyncio import AsyncIOMotorClient
from models import UserUsage, UserData
from safety import check_prompt_safety

# Load environment variables
load_dotenv(override=True)

app = FastAPI()

# Global Runware instance
RUNWARE_API_KEY = os.getenv("RUNWARE_API_KEY")
runware = Runware(api_key=RUNWARE_API_KEY)

# MongoDB and Clerk Configuration
MONGO_URL = os.getenv("MONGO_URL")
DAILY_LIMIT = 20

# Load Clerk Public Key from file (safest)
CLERK_JWT_PUBLIC_KEY = None
if os.path.exists("clerk_public.pem"):
    with open("clerk_public.pem", "r") as f:
        CLERK_JWT_PUBLIC_KEY = f.read().strip()
else:
    # Fallback to env
    CLERK_JWT_PUBLIC_KEY = os.getenv("CLERK_JWT_PUBLIC_KEY")

@app.on_event("startup")
async def startup_event():
    print("\n--- Backend Startup Diagnostics ---")
    print(f"RUNWARE_API_KEY: {'✅ Found' if RUNWARE_API_KEY else '❌ Missing'}")
    print(f"MONGO_URL: {'✅ Found' if MONGO_URL else '❌ Missing'}")
    print(f"CLERK_JWT_PUBLIC_KEY: {'✅ Found' if CLERK_JWT_PUBLIC_KEY else '❌ Missing'}")
    if CLERK_JWT_PUBLIC_KEY:
        print(f"Clerk Key Length: {len(CLERK_JWT_PUBLIC_KEY)} chars")
    print("-----------------------------------\n")
    
    await runware.connect()

# Initialize MongoDB client (global)
if MONGO_URL:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.get_database() 
else:
    print("❌ Critical: MONGO_URL not found!")
    db = None

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not CLERK_JWT_PUBLIC_KEY:
        # For development/safety, if public key is not set, we might want to warn or skip
        # but in production this should be a hard requirement.
        raise HTTPException(status_code=500, detail="CLERK_JWT_PUBLIC_KEY not configured")
    
    token = credentials.credentials
    try:
        # Clerk uses RS256 for JWTs
        payload = jwt.decode(token, CLERK_JWT_PUBLIC_KEY, algorithms=["RS256"])
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {str(e)}")

async def check_limit_and_credits(user_payload: dict = Depends(verify_token)):
    try:
        user_id = user_payload["sub"]
        today = datetime.utcnow().date().isoformat()
        
        # 1. Check Daily Limit
        usage_data = await db.usage.find_one({"user_id": user_id, "date": today})
        if usage_data:
            usage = UserUsage(**usage_data)
            if usage.count >= DAILY_LIMIT:
                raise HTTPException(status_code=429, detail="Daily generation limit reached")
        
        # 2. Check Credits & Update Email
        email = user_payload.get("email") # Get email from Clerk JWT
        
        user_doc = await db.users.find_one({"user_id": user_id})
        if not user_doc:
            # Auto-create user with 3 free credits and email if not exists
            new_user = UserData(user_id=user_id, email=email, credits=3)
            await db.users.insert_one(new_user.model_dump())
            user_doc = new_user.model_dump()
        else:
            # Update email if it changed or was missing
            if email and user_doc.get("email") != email:
                await db.users.update_one({"user_id": user_id}, {"$set": {"email": email}})
        
        user_data = UserData(**user_doc)
        if user_data.credits <= 0:
            raise HTTPException(status_code=402, detail="No credits left")
        
        return user_payload
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in check_limit_and_credits: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def track_usage(user_id: str):
    today = datetime.utcnow().date().isoformat()
    # Update Daily Limit
    await db.usage.update_one(
        {"user_id": user_id, "date": today},
        {"$inc": {"count": 1}},
        upsert=True
    )
    # Deduct Credit and get new count
    result = await db.users.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"credits": -1}},
        return_document=True
    )
    return result.get("credits", 0) if result else 0

@app.get("/profile")
async def get_profile(user: dict = Depends(verify_token)):
    user_id = user["sub"]
    user_doc = await db.users.find_one({"user_id": user_id})
    today = datetime.utcnow().date().isoformat()
    
    if not user_doc:
        # Create user if they don't exist yet
        email = user.get("email")
        new_user = UserData(user_id=user_id, email=email, credits=10)
        await db.users.insert_one(new_user.model_dump())
        user_doc = new_user.model_dump()
    else:
        # Check for date reset
        if user_doc.get("last_ad_date") != today:
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "ads_watched_today": 0,
                    "ad_credits_earned_today": 0,
                    "last_ad_date": today
                }}
            )
            user_doc["ads_watched_today"] = 0
            user_doc["ad_credits_earned_today"] = 0
            user_doc["last_ad_date"] = today
    
    user_data = UserData(**user_doc)
    return {
        "user_id": user_data.user_id,
        "email": user_data.email,
        "credits": user_data.credits,
        "plan": user_data.plan,
        "ads_watched_today": user_data.ads_watched_today,
        "ad_credits_earned_today": user_data.ad_credits_earned_today
    }

@app.post("/add-reward-credits")
async def add_reward_credits(user: dict = Depends(verify_token)):
    user_id = user["sub"]
    today = datetime.utcnow().date().isoformat()
    
    user_doc = await db.users.find_one({"user_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Reset logic if it's a new day
    if user_doc.get("last_ad_date") != today:
        user_doc["ads_watched_today"] = 0
        user_doc["ad_credits_earned_today"] = 0
        user_doc["last_ad_date"] = today
        
    if user_doc.get("ads_watched_today", 0) >= 5:
        raise HTTPException(status_code=429, detail="Daily ad limit reached (5/5)")
        
    # Increment ads watched
    new_ads_watched = user_doc.get("ads_watched_today", 0) + 1
    
    # Check if we should grant credit (limit 3 per day)
    credit_granted = False
    update_data = {
        "ads_watched_today": new_ads_watched,
        "last_ad_date": today
    }
    
    inc_data = {}
    if user_doc.get("ad_credits_earned_today", 0) < 3:
        inc_data["credits"] = 1
        inc_data["ad_credits_earned_today"] = 1
        credit_granted = True
        
    update_op = {"$set": update_data}
    if inc_data:
        update_op["$inc"] = inc_data
        
    result = await db.users.find_one_and_update(
        {"user_id": user_id},
        update_op,
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update credits")
        
    return {
        "success": True,
        "credits": result.get("credits", 0),
        "credit_granted": credit_granted,
        "ads_watched_today": new_ads_watched,
        "ad_credits_earned_today": result.get("ad_credits_earned_today", 0),
        "message": "Reward credit added successfully" if credit_granted else "Ad watched, but daily credit limit reached"
    }

@app.on_event("startup")
async def startup_event():
    await runware.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await runware.disconnect()
    if 'client' in globals() and client:
        client.close()

class T2IRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "1:1" # 1:1, 16:9, 9:16, 4:3, 3:4
    style: Optional[str] = None
    quality: Optional[str] = "medium" # low, medium, high

class I2IRequest(BaseModel):
    prompt: str
    source_url: str
    aspect_ratio: Optional[str] = "1:1"
    style: Optional[str] = None
    quality: Optional[str] = "medium"

class DeleteAccountRequest(BaseModel):
    reason: str

class VideoRequest(BaseModel):
    prompt: str
    source_url: Optional[str] = None
    aspect_ratio: Optional[str] = "16:9"
    duration: Optional[int] = 2
    audio: Optional[bool] = False

def get_dimensions(aspect_ratio: str):
    ratios = {
        "1:1": (1024, 1024),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
        "4:3": (1152, 864),
        "3:4": (864, 1152),
        "2:3": (832, 1216)
    }
    return ratios.get(aspect_ratio, (1024, 1024))

def get_steps(quality: str):
    quality_map = {
        "low": 20,
        "medium": 30,
        "high": 50
    }
    return quality_map.get(quality, 30)

@app.post("/text-to-image")
async def text_to_image(request: T2IRequest, user: dict = Depends(check_limit_and_credits)):
    # Check prompt safety before proceeding (will raise 400 if unsafe)
    check_prompt_safety(request.prompt)

    try:
        user_id = user["sub"]
        width, height = get_dimensions(request.aspect_ratio)
        steps = get_steps(request.quality)
        
        # Combine prompt with style
        final_prompt = request.prompt
        if request.style:
            final_prompt = f"{request.prompt}, in the style of {request.style}"

        request_image = IImageInference(
            positivePrompt=final_prompt,
            negativePrompt="blurry, low quality, distorted face, bad anatomy",
            model="runware:400@6", # FLUX.2 [klein] 9B KV
            numberResults=1,
            height=height,
            width=width,
            steps=steps,
            includeCost=True
        )
        images = await runware.imageInference(requestImage=request_image)
        if not images:
            raise HTTPException(status_code=500, detail="No image generated")
        
        # Track usage after successful generation
        remaining_credits = await track_usage(user_id)
        
        return {
            "url": images[0].imageURL,
            "cost": images[0].cost,
            "remaining_credits": remaining_credits
        }
    except Exception as e:
        print(f"ERROR in text_to_image: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/image-to-image")
async def image_to_image(request: I2IRequest, user: dict = Depends(check_limit_and_credits)):
    # Check prompt safety before proceeding (will raise 400 if unsafe)
    check_prompt_safety(request.prompt)

    try:
        user_id = user["sub"]
        width, height = get_dimensions(request.aspect_ratio)
        
        final_prompt = request.prompt
        if request.style:
            final_prompt = f"{request.prompt}, in the style of {request.style}"

        # FLUX.2 uses referenceImages for image-to-image instead of seedImage
        # Note: FLUX models do not support the 'strength' parameter.
        request_image = IImageInference(
            positivePrompt=final_prompt,
            negativePrompt="blurry, low quality, distorted face, bad anatomy",
            model="runware:400@6", # FLUX.2 [klein] 9B KV
            referenceImages=[request.source_url],
            numberResults=1,
            height=height,
            width=width,
            steps=4, # FLUX turbo variants use 4 steps
            CFGScale=4.0, # FLUX standard CFG is around 4
            outputQuality=85,
            includeCost=True
        )
        images = await runware.imageInference(requestImage=request_image)
        if not images:
            raise HTTPException(status_code=500, detail="No image generated")
        
        # Track usage after successful generation
        remaining_credits = await track_usage(user_id)

        return {
            "url": images[0].imageURL,
            "cost": images[0].cost,
            "remaining_credits": remaining_credits
        }
    except Exception as e:
        print(f"ERROR in image_to_image: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/request-delete-account")
async def request_delete_account(request: DeleteAccountRequest, user: dict = Depends(verify_token)):
    try:
        user_id = user["sub"]
        email = user.get("email", "")
        
        delete_request = {
            "user_id": user_id,
            "email": email,
            "reason": request.reason,
            "status": "pending",
            "requested_at": datetime.utcnow().isoformat()
        }
        
        await db.delete_requests.insert_one(delete_request)
        
        return {"success": True, "message": "Delete account request submitted successfully"}
    except Exception as e:
        print(f"ERROR in request_delete_account: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# async def track_video_usage(user_id: str):
#     today = datetime.utcnow().date().isoformat()
#     # Update Daily Limit
#     await db.usage.update_one(
#         {"user_id": user_id, "date": today},
#         {"$inc": {"count": 1}},
#         upsert=True
#     )
#     # Deduct 5 Credits and get new count
#     result = await db.users.find_one_and_update(
#         {"user_id": user_id},
#         {"$inc": {"credits": -5}},
#         return_document=True
#     )
#     return result.get("credits", 0) if result else 0
# 
# @app.post("/generate-video")
# async def generate_video(request: VideoRequest, user: dict = Depends(check_limit_and_credits)):
#     try:
#         user_id = user["sub"]
#         
#         # Check if user has at least 5 credits
#         user_doc = await db.users.find_one({"user_id": user_id})
#         if not user_doc or user_doc.get("credits", 0) < 5:
#             raise HTTPException(status_code=402, detail="Insufficient credits for video generation (Requires 5 credits)")
#             
#         width, height = get_dimensions(request.aspect_ratio)
#         
#         # Note: "runware:bytedance-seedance-1-5-pro" or just "bytedance-seedance-1-5-pro"
#         # Often Runware models might need "runware:xx" but "bytedance-seedance-1-5-pro" works as model string.
#         
#         video_args = {
#             "positivePrompt": request.prompt,
#             "negativePrompt": "blurry, low quality, distorted",
#             "model": "runware:bytedance-seedance-1-5-pro",
#             "height": height,
#             "width": width,
#             "duration": request.duration,
#             "includeCost": True
#         }
#         
#         if request.source_url:
#             video_args["referenceImages"] = [request.source_url]
#             
#         request_video = IVideoInference(**video_args)
#         
#         # videoInference returns a list of videos
#         videos = await runware.videoInference(requestVideo=request_video)
#         if not videos:
#             raise HTTPException(status_code=500, detail="No video generated")
#         
#         # Track usage after successful generation (cost 5 credits)
#         remaining_credits = await track_video_usage(user_id)
# 
#         return {
#             "url": videos[0].videoURL,
#             "cost": videos[0].cost,
#             "remaining_credits": remaining_credits
#         }
#     except Exception as e:
#         print(f"ERROR in generate_video: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
