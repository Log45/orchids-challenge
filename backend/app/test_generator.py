from scrape import clone_website
from generator import WebsiteGenerator, GeneratorConfig
import os
from dotenv import load_dotenv
import anthropic
import openai
import tiktoken

load_dotenv()

anthropic_config = GeneratorConfig(
    client=anthropic.Anthropic(api_key=os.getenv("CLAUDE_KEY")),
    model_heavy="claude-opus-4-20250514",
    model_js="claude-sonnet-4-20250514",
    model_css="claude-3-7-sonnet-20250219",
    max_tokens=5000,
    encoding=tiktoken.get_encoding("cl100k_base"),
    rate_limit_delay=1
)

openai_config = GeneratorConfig(
    client=openai.OpenAI(api_key=os.getenv("OPENAI_KEY")),
    model_heavy="gpt-4.1",
    model_js="o4-mini",
    model_css="o4-mini",
    max_tokens=10000,
    encoding=tiktoken.get_encoding("cl100k_base"),
    rate_limit_delay=1
)


def test_generator():
    website_dir = os.path.abspath("cloned_site/docs.hyperbrowser.ai_/")
    generator = WebsiteGenerator(config=openai_config)
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