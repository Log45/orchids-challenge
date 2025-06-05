from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import logging
from scrape import clone_website
import os
import sys
import asyncio

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

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/websites")
def create_item(website: Website):
    try:
        logger.info(f"Received request to clone website: {website.url}")
        # webscrape the url of the website 
        website_dir = os.path.abspath(clone_website(str(website.url)))
        logger.info(f"Successfully cloned website to: {website_dir}")
        # TODO: pipe data from the website to the LLM
        # TODO: clone the website with the LLM and preview the result on the frontend
        return {"website": website_dir}
    except Exception as e:
        logger.error(f"Error cloning website: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
