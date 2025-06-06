from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import logging
from scrape import clone_website
from generator import WebsiteGenerator
import os
import sys
import asyncio
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Website(BaseModel):
    url: HttpUrl

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the website generator
generator = WebsiteGenerator(api_key=os.getenv("CLAUDE_KEY"))

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/websites")
def create_item(website: Website):
    try:
        logger.info(f"Received request to clone website: {website.url}")
        
        # Step 1: Scrape the website
        website_dir = os.path.abspath(clone_website(str(website.url)))
        logger.info(f"Successfully cloned website to: {website_dir}")
        
        # Step 2: Generate modern version using Claude
        generated_sections = generator.generate_website(website_dir)
        logger.info("Successfully generated modern version of the website")
        
        # Step 3: Save the generated website
        generated_dir = generator.save_website(website_dir, generated_sections)
        logger.info(f"Successfully saved generated website to: {generated_dir}")
        
        return {
            "original_dir": website_dir,
            "generated_dir": generated_dir,
            "message": "Website successfully cloned and modernized with all assets"
        }
        
    except Exception as e:
        logger.error(f"Error processing website: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
