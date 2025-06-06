from scrape import clone_website
from generator import WebsiteGenerator
import os
from dotenv import load_dotenv

load_dotenv()

def test_generator():
    website_dir = os.path.abspath("cloned_site/docs.hyperbrowser.ai_/")
    generator = WebsiteGenerator(api_key=os.getenv("CLAUDE_KEY"))
    print("Generating website...")
    generated_sections = generator.generate_website(website_dir)
    print("Website generated...")
    generated_dir = generator.save_website(website_dir, generated_sections)
    print("Website generated and saved to: ", generated_dir)


    
    
def test_pipeline(url: str):
    website_dir = os.path.abspath(clone_website(url))
    print("Website cloned to: ", website_dir)
    generator = WebsiteGenerator(api_key=os.getenv("CLAUDE_KEY"))
    print("Generating website...")
    generated_sections = generator.generate_website(website_dir)
    print("Website generated...")
    generated_dir = generator.save_website(website_dir, generated_sections)
    print("Website generated and saved to: ", generated_dir)

if __name__ == "__main__":
    test_generator()