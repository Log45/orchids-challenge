from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import logging
from scrape import clone_website
from generator import WebsiteGenerator
import os
import sys
import asyncio
from pathlib import Path
from fastapi.responses import FileResponse
import re

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

# Mount the cloned_site directory for static file serving
app.mount("/static", StaticFiles(directory="cloned_site", html=True), name="static")

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/websites")
def create_website(website: Website):
    try:
        logger.info(f"Received request to clone website: {website.url}")
        
        # Step 1: Scrape the website
        website_dir = os.path.abspath(clone_website(str(website.url)))
        logger.info(f"Successfully cloned website to: {website_dir}")
        
        # Return relative paths for the frontend
        original_dir = os.path.relpath(website_dir, os.getcwd())
        
        return {
            "original_dir": original_dir,
            "message": "Website successfully cloned and modernized with all assets"
        }
        
    except Exception as e:
        logger.error(f"Error processing website: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# THIS MUST BE BEFORE THE CATCH-ALL GET
# Add a catch-all POST route to handle API requests from the cloned site
@app.post("/{path:path}")
def handle_api_requests(path: str):
    logger.info(f"API POST request to '{path}' blocked and returned empty response.")
    return {}

# This new catch-all GET route handles assets requested from the root path.
# It uses the 'Referer' header to find the correct cloned site directory.
# THIS MUST BE THE LAST GET ROUTE defined in the app.
@app.get("/{path:path}")
async def serve_cloned_assets(request: Request, path: str):
    referer = request.headers.get("referer")
    
    # First, try to find the asset using the referer URL
    if referer:
        # e.g., http://.../static/youtube.com_/index.html -> youtube.com_
        match = re.search(r"/static/([^/]+)", referer)
        if match:
            domain_dir = match.group(1)
            file_path = Path("cloned_site") / domain_dir / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

    # As a fallback, if referer fails, search all cloned site directories
    cloned_site_path = Path("cloned_site")
    if cloned_site_path.exists():
        for domain_dir_path in cloned_site_path.iterdir():
            if domain_dir_path.is_dir():
                file_path = domain_dir_path / path
                if file_path.exists() and file_path.is_file():
                    logger.warning(f"Served '{path}' using fallback search to '{domain_dir_path.name}'")
                    return FileResponse(file_path)

    raise HTTPException(status_code=404, detail=f"File not found: {path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
