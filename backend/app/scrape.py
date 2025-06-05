import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from dotenv import load_dotenv
from hyperbrowser import Hyperbrowser
from urllib.parse import urlparse
from pathlib import Path
import logging
import traceback
import sys
import time
import asyncio
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "cloned_site"
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables from .env file
load_dotenv()
client = Hyperbrowser(api_key=os.getenv("HYPERBROWSER_API_KEY"))

def save_response(response, url):
    output_dir = OUTPUT_DIR + "/" + url.replace("https://", "").replace("http://", "").replace("/", "_")
    try:
        url = response.url
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1]
        if not ext:
            return  # skip if no file extension

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            return  # we save the main HTML separately

        filename = Path(parsed.path.lstrip("/"))
        save_path = Path(output_dir) / filename

        save_path.parent.mkdir(parents=True, exist_ok=True)
        body = response.body()
        with open(save_path, "wb") as f:
            f.write(body)
        logger.info(f"Saved asset: {url} -> {save_path}")
    except Exception as e:
        logger.error(f"Failed to save {response.url}: {str(e)}\n{traceback.format_exc()}")

def clone_website(url) -> str:
    output_dir = OUTPUT_DIR + "/" + url.replace("https://", "").replace("http://", "").replace("/", "_")
    os.makedirs(output_dir, exist_ok=True)
    session = client.sessions.create()
    
    try:
        with sync_playwright() as p:
            try:
                logger.info(f"Connecting to {session.ws_endpoint}")
                browser = p.chromium.connect_over_cdp(session.ws_endpoint)
                context = browser.new_context()
                page = context.new_page()
                
                # Set up response handler
                def handle_response(response):
                    save_response(response, url)
                
                page.on("response", handle_response)

                try:
                    logger.info(f"Navigating to {url}")
                    page.goto(url, wait_until="networkidle", timeout=30000)  # 30 second timeout
                    
                    # Save the main HTML
                    content = page.content()
                    with open(f"{output_dir}/index.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info(f"Saved main page: {url} -> {output_dir}/index.html")

                    # Optional: screenshot
                    page.screenshot(path=f"{output_dir}/screenshot.png", full_page=True)
                    logger.info(f"Saved screenshot: {output_dir}/screenshot.png")

                except PlaywrightTimeoutError as e:
                    logger.error(f"Timeout while loading {url}: {str(e)}\n{traceback.format_exc()}")
                    raise
                except PlaywrightError as e:
                    logger.error(f"Playwright error during page processing: {str(e)}\n{traceback.format_exc()}")
                    raise
                except Exception as e:
                    logger.error(f"Error during page processing: {str(e)}\n{traceback.format_exc()}")
                    raise
                finally:
                    context.close()
                    browser.close()
            except PlaywrightError as e:
                logger.error(f"Playwright browser error: {str(e)}\n{traceback.format_exc()}")
                raise
            except Exception as e:
                logger.error(f"Browser setup error: {str(e)}\n{traceback.format_exc()}")
                raise
    except Exception as e:
        logger.error(f"General error: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        time.sleep(2)
        client.sessions.stop(session.id)
    return output_dir

if __name__ == "__main__":
    target_url = "https://docs.hyperbrowser.ai/"  # change to your target
    clone_website(target_url)