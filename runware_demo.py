import asyncio
import os
from runware import Runware, IImageInference
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def text_to_image(runware: Runware):
    print("\n--- Running Text-to-Image ---")
    request_image = IImageInference(
        positivePrompt="a futuristic city with neon lights, highly detailed, digital art",
        model="runware:400@6", # FLUX.2 [klein] 9B KV
        numberResults=1,
        height=1024,
        width=1024,
    )

    images = await runware.imageInference(requestImage=request_image)
    for image in images:
        print(f"Generated Image URL: {image.imageURL}")
    return images[0].imageURL if images else None

async def image_to_image(runware: Runware, source_image_url: str):
    print("\n--- Running Image-to-Image ---")
    # Image-to-Image uses seedImage and strength
    # strength: 0.0 to 1.0 (lower means closer to source image, higher means closer to prompt)
    request_image = IImageInference(
        positivePrompt="same futuristic city but in daytime with bright sunlight",
        model="runware:400@6", # FLUX.2 [klein] 9B KV
        seedImage=source_image_url,
        strength=0.6, 
        numberResults=1,
        height=1024,
        width=1024,
    )

    images = await runware.imageInference(requestImage=request_image)
    for image in images:
        print(f"Img2Img Result URL: {image.imageURL}")

async def main():
    api_key = os.getenv("RUNWARE_API_KEY")
    if not api_key:
        print("Error: RUNWARE_API_KEY not found in .env file.")
        return

    runware = Runware(api_key=api_key)
    await runware.connect()

    try:
        # 1. Text to Image
        generated_url = await text_to_image(runware)
        
        # 2. Image to Image (using the result of the first generation as source)
        if generated_url:
            await image_to_image(runware, generated_url)
        else:
            # Fallback if text-to-image failed to return a URL
            print("Skipping Img2Img as no source image was generated.")

    finally:
        await runware.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
