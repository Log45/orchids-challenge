import os
import anthropic
from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Union
import shutil
from bs4 import BeautifulSoup
import re
import json
import tiktoken
import time
import hashlib
import shelve
import concurrent.futures
from dataclasses import dataclass
from functools import partial

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class GeneratorConfig:
    client: Union[anthropic.Anthropic, OpenAI]
    model_heavy: str
    model_js: str
    model_css: str
    max_tokens: int
    encoding: tiktoken.Encoding
    rate_limit_delay: int
    
    def generate(self, prompt: str, model: str = None, max_tokens: int = None) -> Union[anthropic.Anthropic.messages, ChatCompletion]:
        """API Agnostic method to generate text using the client."""
        if model is None:
            model = self.model_js
        if max_tokens is None:
            max_tokens = self.max_tokens
        if isinstance(self.client, anthropic.Anthropic):
            return self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
        elif isinstance(self.client, OpenAI):
            return self.client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            raise ValueError(f"Unsupported client type: {type(self.client)}")

class WebsiteGenerator:
    def __init__(self, config: GeneratorConfig):
        logger.info("Initializing WebsiteGenerator")
        self.config = config
        self.client = config.client
        self.model_heavy = config.model_heavy
        self.model_js = config.model_js
        self.model_css = config.model_css
        self.max_tokens = config.max_tokens
        self.encoding = config.encoding
        self.rate_limit_delay = config.rate_limit_delay
        self.cache = shelve.open("api_cache")
        logger.info("WebsiteGenerator initialized successfully")

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        count = len(self.encoding.encode(text))
        logger.debug(f"Token count: {count}")
        return count

    def _strip_comments(self, text: str, filetype: str) -> str:
        """Strip comments from CSS or JavaScript code."""
        logger.debug(f"Stripping comments from {filetype}")
        if filetype == 'css':
            return re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        if filetype == 'js':
            return re.sub(r'//.*?$|/\*.*?\*/', '', text, flags=re.DOTALL | re.MULTILINE)
        return text

    def _chunk_content(self, content: str, max_tokens: int) -> List[str]:
        """Split content into chunks that fit within token limit."""
        logger.debug(f"Chunking content with max_tokens={max_tokens}")
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        lines = content.split('\n')
        for line in lines:
            line_tokens = self._count_tokens(line)
            if current_tokens + line_tokens > max_tokens:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_tokens = line_tokens
            else:
                current_chunk.append(line)
                current_tokens += line_tokens
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        logger.info(f"Split content into {len(chunks)} chunks")
        return chunks

    def _read_files(self, website_dir: str) -> Tuple[str, str, str, List[Path]]:
        """Read HTML, CSS, JS files and collect all assets from the website directory."""
        logger.info(f"Reading files from {website_dir}")
        website_path = Path(website_dir)
        html_path = website_path / "index.html"
        
        if not html_path.exists():
            logger.error(f"HTML file not found at {html_path}")
            raise FileNotFoundError(f"HTML file not found at {html_path}")
        
        logger.info("Reading HTML file")
        html_content = html_path.read_text(encoding='utf-8')
        
        # Find all CSS and JS files
        css_files = list(website_path.rglob("*.css"))
        js_files = list(website_path.rglob("*.js"))
        
        logger.info(f"Found {len(css_files)} CSS files and {len(js_files)} JS files")
        
        css_content = ""
        for css_file in css_files:
            raw = css_file.read_text(encoding='utf-8')
            stripped = self._strip_comments(raw, 'css')
            if self._count_tokens(stripped) > 100:
                logger.debug(f"Including CSS file: {css_file}")
                css_content += f"\n/* {css_file.name} */\n" + stripped
        
        js_content = ""
        for js_file in js_files:
            raw = js_file.read_text(encoding='utf-8')
            stripped = self._strip_comments(raw, 'js')
            if self._count_tokens(stripped) > 100:
                logger.debug(f"Including JS file: {js_file}")
                js_content += f"\n// {js_file.name}\n" + stripped
        
        asset_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot'}
        asset_files = []
        for ext in asset_extensions:
            asset_files.extend(website_path.rglob(f"*{ext}"))
        
        logger.info(f"Found {len(asset_files)} asset files")
        return html_content, css_content, js_content, asset_files

    def _make_api_request(self, prompt: str, model: str = None, max_tokens: int = 8000) -> str:
        """Make an API request with retry logic and rate limiting."""
        model = model or self.model_js
        key = hashlib.md5((model + prompt).encode()).hexdigest()
        
        if key in self.cache:
            logger.info(f"Cache hit for model={model}")
            return self.cache[key]
        
        logger.info(f"Making API call with model={model}")
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        max_retries = 5
        base_delay = 5  # Increased base delay
        max_delay = 60  # Increased max delay
        
        for attempt in range(max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                logger.debug(f"API request attempt {attempt + 1}/{max_retries}")
                response = self.config.generate(prompt, model, max_tokens)
                text = response.content[0].text if isinstance(self.client, anthropic.Anthropic) else response.choices[0].message.content
                self.cache[key] = text
                logger.debug("API response cached")
                return text
                
            except Exception as e:
                error_str = str(e).lower()
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    if "rate_limit_error" in error_str:
                        logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                    elif "overloaded" in error_str or "529" in error_str:
                        logger.warning(f"API overloaded (529), attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                        # Add extra delay for overload errors
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.warning(f"API error: {str(e)}, attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                    
                    logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    continue
                logger.error(f"All API request attempts failed: {str(e)}")
                raise

    def _generate_css_chunk(self, chunk: str, index: int, total: int) -> str:
        """Generate CSS for a single chunk."""
        try:
            prompt = f"""Create modern, optimized CSS for this website (part {index+1}/{total}):

CSS:
```css
{chunk}
```

Requirements:
- Create modern, optimized CSS
- Add vendor prefixes where needed
- Optimize for performance
- Ensure browser compatibility
- Include helpful comments
"""
            return self._make_api_request(prompt, model=self.model_css)
        except Exception as e:
            logger.error(f"Error generating CSS chunk {index+1}: {str(e)}")
            return chunk  # Fallback to original chunk

    def _generate_js_chunk(self, chunk: str, index: int, total: int) -> str:
        """Generate JavaScript for a single chunk."""
        try:
            prompt = f"""Create modern, optimized JavaScript for this website (part {index+1}/{total}):

JavaScript:
```javascript
{chunk}
```

Requirements:
- Create modern, optimized JavaScript
- Include necessary polyfills
- Optimize for performance
- Ensure browser compatibility
- Include helpful comments
"""
            return self._make_api_request(prompt, model=self.model_js)
        except Exception as e:
            logger.error(f"Error generating JS chunk {index+1}: {str(e)}")
            return chunk  # Fallback to original chunk

    def _analyze_html_structure(self, html_content: str) -> dict:
        """Analyze the overall structure of the HTML file."""
        logger.info("Analyzing HTML structure")
        
        try:
            messages = [
                {"role": "system", "content": """You are an expert web developer agent specialized in analyzing website structure.
Your task is to analyze the provided HTML and create a structural summary.
Focus on:
1. Main sections and their hierarchy
2. Key components and their relationships
3. Critical functionality
4. Important assets and dependencies

Return a JSON object with the structure analysis."""},
                {"role": "user", "content": f"""Please analyze this HTML structure:

```html
{html_content}
```

Return a JSON object with:
1. main_sections: List of main sections with their purposes
2. key_components: List of important components and their roles
3. critical_functionality: List of critical features
4. dependencies: List of important assets and external resources"""}
            ]

            if isinstance(self.client, anthropic.Anthropic):
                response = self.client.messages.create(
                    model=self.model_heavy,
                    max_tokens=4000,
                    messages=messages
                )
                content = response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.model_heavy,
                    max_tokens=4000,
                    messages=messages
                )
                content = response.choices[0].message.content

            # Extract JSON from the response
            try:
                structure = json.loads(content)
                logger.info("Successfully analyzed HTML structure")
                return structure
            except json.JSONDecodeError:
                logger.warning("Failed to parse structure analysis as JSON")
                return {}

        except Exception as e:
            logger.error(f"Error analyzing HTML structure: {str(e)}")
            return {}

    def _process_html_section(self, section: str, context: dict) -> str:
        """Process a single HTML section with context."""
        logger.info("Processing HTML section")
        
        try:
            messages = [
                {"role": "system", "content": """You are an expert web developer agent specialized in modernizing website sections.
Your task is to optimize this HTML section while maintaining its functionality.
Use the provided context to ensure consistency with the overall structure."""},
                {"role": "user", "content": f"""Context from overall structure:
```json
{json.dumps(context, indent=2)}
```

Please optimize this HTML section:
```html
{section}
```

Requirements:
1. Maintain functionality and references
2. Use semantic HTML5 elements
3. Add ARIA attributes where needed
4. Keep class names and IDs
5. Ensure backward compatibility
6. Optimize for performance
7. Add helpful comments

Return the optimized HTML wrapped in ```html and ``` markers."""}
            ]

            if isinstance(self.client, anthropic.Anthropic):
                response = self.client.messages.create(
                    model=self.model_heavy,
                    max_tokens=4000,
                    messages=messages
                )
                content = response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.model_heavy,
                    max_tokens=4000,
                    messages=messages
                )
                content = response.choices[0].message.content

            # Extract HTML from markdown code blocks
            html_match = re.search(r'```html\n(.*?)\n```', content, re.DOTALL)
            if html_match:
                optimized_section = html_match.group(1).strip()
                logger.info("Successfully processed HTML section")
                return optimized_section
            else:
                logger.warning("No HTML content found in section response")
                return section

        except Exception as e:
            logger.error(f"Error processing HTML section: {str(e)}")
            return section

    def _generate_html(self, html_content: str) -> str:
        """Generate optimized HTML using a hierarchical approach."""
        logger.info("Starting HTML optimization using hierarchical approach")
        
        try:
            # Step 1: Analyze overall structure
            structure = self._analyze_html_structure(html_content)
            if not structure:
                logger.warning("Failed to analyze structure, falling back to direct processing")
                return self._process_entire_html(html_content)

            # Step 2: Split HTML into logical sections
            soup = BeautifulSoup(html_content, 'html.parser')
            sections = []
            
            # Extract main sections
            for section in soup.find_all(['header', 'main', 'footer', 'nav', 'section', 'article']):
                sections.append(str(section))
            
            # If no sections found, split by divs
            if not sections:
                for div in soup.find_all('div', recursive=False):
                    sections.append(str(div))

            # Step 3: Process each section with context
            processed_sections = []
            for section in sections:
                processed_section = self._process_html_section(section, structure)
                processed_sections.append(processed_section)

            # Step 4: Combine processed sections
            optimized_html = "\n".join(processed_sections)
            logger.info("Successfully generated optimized HTML")
            return optimized_html

        except Exception as e:
            logger.error(f"Error during HTML optimization: {str(e)}")
            logger.info("Falling back to original HTML")
            return html_content

    def _process_entire_html(self, html_content: str) -> str:
        """Fallback method to process the entire HTML at once."""
        logger.info("Processing entire HTML at once")
        
        try:
            messages = [
                {"role": "system", "content": """You are an expert web developer agent specialized in cloning and modernizing websites. 
Your task is to analyze the provided HTML and create a modern, optimized version while maintaining all functionality.
Focus on:
1. Semantic HTML5 structure
2. Accessibility (ARIA attributes)
3. Modern best practices
4. Performance optimization
5. Browser compatibility

Respond with the complete, optimized HTML wrapped in ```html and ``` markers."""},
                {"role": "user", "content": f"""Please analyze and optimize this HTML code:

```html
{html_content}
```

Requirements:
1. Maintain all functionality and references
2. Use semantic HTML5 elements
3. Add ARIA attributes where needed
4. Keep all class names and IDs
5. Ensure backward compatibility
6. Optimize for performance
7. Add helpful comments

Return the complete, optimized HTML wrapped in ```html and ``` markers."""}
            ]

            if isinstance(self.client, anthropic.Anthropic):
                response = self.client.messages.create(
                    model=self.model_heavy,
                    max_tokens=10000,
                    messages=messages
                )
                content = response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.model_heavy,
                    max_tokens=10000,
                    messages=messages
                )
                content = response.choices[0].message.content
                
            # Extract HTML from markdown code blocks
            html_match = re.search(r'```html\n(.*?)\n```', content, re.DOTALL)
            if html_match:
                optimized_html = html_match.group(1).strip()
                logger.info("Successfully generated optimized HTML")
                return optimized_html
            else:
                logger.warning("No HTML content found in API response, using original HTML")
                return html_content
                
        except Exception as e:
            logger.error(f"Error during HTML optimization: {str(e)}")
            logger.info("Falling back to original HTML")
            return html_content

    def _generate_global_resources(self, html_content: str, css_content: str, js_content: str) -> Dict[str, str]:
        """Generate global resources (shared CSS and JS) for the website."""
        logger.info("Starting website optimization")
        
        try:
            # Generate optimized HTML using the agent
            optimized_html = self._generate_html(html_content)
            
            logger.info("Website optimization completed successfully")
            return {
                "html": optimized_html,
                "css": css_content,
                "js": js_content
            }
            
        except Exception as e:
            logger.error(f"Error during website optimization: {str(e)}")
            logger.info("Falling back to original content")
            return {
                "html": html_content,
                "css": css_content,
                "js": js_content
            }

    def generate_website(self, website_dir: str) -> Dict[str, str]:
        """Generate a modern version of the website using Claude."""
        logger.info(f"Starting website generation for {website_dir}")
        try:
            # Read the original website files and collect assets
            html_content, css_content, js_content, asset_files = self._read_files(website_dir)
            logger.info("Successfully read all website files")
            
            # Generate optimized version
            logger.info("Generating optimized version")
            sections = self._generate_global_resources(html_content, css_content, js_content)
            
            # Add asset files to the response
            sections["assets"] = [str(asset) for asset in asset_files]
            logger.info(f"Added {len(asset_files)} assets to the response")
            
            logger.info("Website generation completed successfully")
            return sections

        except Exception as e:
            logger.error(f"Error generating website: {str(e)}")
            raise

    def close(self):
        """Close the cache and clean up resources."""
        logger.info("Closing WebsiteGenerator")
        self.cache.close()
        logger.info("Cache closed successfully")

    def save_website(self, website_dir: str, sections: Dict[str, str], output_dir = "./generated_website") -> str:
        """Save the generated website files to the specified directory."""
        logger.info(f"Saving generated website to {output_dir}")
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save HTML
            html_path = output_path / "index.html"
            logger.info(f"Saving HTML to {html_path}")
            html_path.write_text(sections["html"], encoding='utf-8')
            
            # Save CSS
            css_path = output_path / "styles.css"
            logger.info(f"Saving CSS to {css_path}")
            css_path.write_text(sections["css"], encoding='utf-8')
            
            # Save JS
            js_path = output_path / "script.js"
            logger.info(f"Saving JavaScript to {js_path}")
            js_path.write_text(sections["js"], encoding='utf-8')
            
            # Copy assets
            if "assets" in sections:
                logger.info("Copying assets")
                for asset_path in sections["assets"]:
                    asset = Path(asset_path)
                    if asset.exists():
                        dest = output_path / asset.name
                        logger.debug(f"Copying {asset} to {dest}")
                        shutil.copy2(asset, dest)
            
            logger.info("Website saved successfully")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error saving website: {str(e)}")
            raise 