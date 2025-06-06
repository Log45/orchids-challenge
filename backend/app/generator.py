import os
import anthropic
from pathlib import Path
import logging
from typing import Dict, List, Tuple
import shutil
from bs4 import BeautifulSoup
import re
import json
import tiktoken
import time
import hashlib
import shelve
import concurrent.futures
from functools import partial

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class WebsiteGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_heavy = "claude-opus-4-20250514"
        self.model_js = "claude-sonnet-4-20250514"  # Better for JavaScript
        self.model_css = "claude-3-7-sonnet-20250219"  # Good enough for CSS
        self.max_tokens = 5000
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.rate_limit_delay = 1
        self.cache = shelve.open("api_cache")
        logger.info("Initialized WebsiteGenerator")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _strip_comments(self, text: str, filetype: str) -> str:
        logger.debug(f"Stripping comments from {filetype}")
        if filetype == 'css':
            return re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        if filetype == 'js':
            return re.sub(r'//.*?$|/\*.*?\*/', '', text, flags=re.DOTALL | re.MULTILINE)
        return text

    def _chunk_content(self, content: str, max_tokens: int) -> List[str]:
        logger.debug("Chunking content")
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
        logger.info(f"Reading files from {website_dir}")
        website_path = Path(website_dir)
        html_path = website_path / "index.html"
        css_files = list(website_path.rglob("*.css"))
        js_files = list(website_path.rglob("*.js"))

        html_content = html_path.read_text(encoding='utf-8') if html_path.exists() else ""

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

        logger.info(f"Found {len(css_files)} CSS, {len(js_files)} JS, {len(asset_files)} asset files")
        return html_content, css_content, js_content, asset_files

    def _make_api_request(self, prompt: str, model: str = None, max_tokens: int = 4000) -> str:
        model = model or self.model_js  # Default to JS model
        key = hashlib.md5((model + prompt).encode()).hexdigest()
        
        # Check cache first
        if key in self.cache:
            logger.info(f"Cache hit for model={model}")
            return self.cache[key]
            
        logger.info(f"Making API call with model={model}")
        
        # Retry logic for both rate limits and overload errors
        max_retries = 5
        base_delay = 2
        max_delay = 30
        
        for attempt in range(max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text
                self.cache[key] = text
                logger.debug("API response cached")
                return text
                
            except Exception as e:
                error_str = str(e).lower()
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff, but cap it
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    if "rate_limit_error" in error_str:
                        logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                    elif "overloaded" in error_str:
                        logger.warning(f"API overloaded, attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                    else:
                        logger.warning(f"API error: {str(e)}, attempt {attempt + 1}/{max_retries}, waiting {delay}s")
                    
                    time.sleep(delay)
                    continue
                raise  # Re-raise if out of retries

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

    def _generate_global_resources(self, html_content: str, css_content: str, js_content: str) -> Dict[str, str]:
        """Generate global resources (shared CSS and JS) for the website in parallel."""
        logger.info("Generating global CSS and JS resources")
        
        # Split into smaller chunks to reduce load
        css_chunks = self._chunk_content(css_content, self.max_tokens // 2)
        js_chunks = self._chunk_content(js_content, self.max_tokens // 2)
        
        # Create partial functions with fixed arguments
        generate_css = partial(self._generate_css_chunk, total=len(css_chunks))
        generate_js = partial(self._generate_js_chunk, total=len(js_chunks))
        
        # Process chunks in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit CSS and JS generation tasks
            css_futures = [executor.submit(generate_css, chunk, i) 
                          for i, chunk in enumerate(css_chunks)]
            js_futures = [executor.submit(generate_js, chunk, i) 
                         for i, chunk in enumerate(js_chunks)]
            
            # Collect results as they complete
            generated_css = []
            generated_js = []
            
            # Process CSS results
            for future in concurrent.futures.as_completed(css_futures):
                try:
                    result = future.result()
                    generated_css.append(result)
                except Exception as e:
                    logger.error(f"Error in CSS generation: {str(e)}")
                    # Find the original chunk that failed
                    index = css_futures.index(future)
                    generated_css.append(css_chunks[index])
            
            # Process JS results
            for future in concurrent.futures.as_completed(js_futures):
                try:
                    result = future.result()
                    generated_js.append(result)
                except Exception as e:
                    logger.error(f"Error in JS generation: {str(e)}")
                    # Find the original chunk that failed
                    index = js_futures.index(future)
                    generated_js.append(js_chunks[index])
        
        return {
            "css": "\n".join(generated_css),
            "js": "\n".join(generated_js)
        }

    def close(self):
        self.cache.close()

    def _generate_component(self, component: Dict[str, str]) -> str:
        """Generate a modern version of a web component using Claude."""
        prompt = f"""Create a modern, clean version of this web component:

Component Type: {component['type']}
Component ID: {component['id']}
Component Classes: {', '.join(component['classes'])}

HTML:
```html
{component['html']}
```

CSS:
```css
{component['css']}
```

JavaScript:
```javascript
{component['js']}
```

Requirements:
- Maintain the same functionality
- Use modern best practices
- Make it responsive
- Add helpful comments
- Use semantic HTML5 with fallbacks for older browsers
- Ensure accessibility
- Optimize performance
- Preserve all asset references (images, fonts, etc.)
- Include necessary polyfills or fallbacks for older browsers
- Use feature detection instead of browser detection
- Ensure graceful degradation for older browsers
- Maintain consistency with the global styles and scripts
"""

        try:
            return self._make_api_request(prompt, max_tokens=2000)
        except Exception as e:
            logger.error(f"Error generating component: {str(e)}")
            # If we fail, return the original component
            return component['html']

    def generate_website(self, website_dir: str) -> Dict[str, str]:
        """Generate a modern version of the website using Claude."""
        try:
            # Read the original website files and collect assets
            html_content, css_content, js_content, asset_files = self._read_files(website_dir)
            
            # Store current CSS and JS for component analysis
            self.current_css = css_content
            self.current_js = js_content
            
            # Step 1: Generate global resources
            logger.info("Generating global resources...")
            global_resources = self._generate_global_resources(html_content, css_content, js_content)
            
            # Step 2: Identify and generate components
            logger.info("Identifying components...")
            components = self._identify_components(html_content)
            generated_components = []
            
            for i, component in enumerate(components):
                logger.info(f"Generating component {i+1}/{len(components)}")
                generated = self._generate_component(component)
                generated_components.append({
                    'original': component,
                    'generated': generated
                })
            
            # Step 3: Integrate everything
            logger.info("Integrating components...")
            integration_prompt = f"""Integrate these components into a complete website:

Global CSS:
```css
{global_resources['css']}
```

Global JavaScript:
```javascript
{global_resources['js']}
```

Components:
{json.dumps(generated_components, indent=2)}

Requirements:
- Create a complete, modern website
- Maintain component relationships
- Ensure proper integration of global resources
- Preserve all functionality
- Optimize performance
- Ensure browser compatibility
- Separate the response into HTML, CSS, and JavaScript sections
"""

            final_response = self._make_api_request(integration_prompt)
            sections = self._parse_response_sections(final_response)
            
            # Add asset files to the response
            sections["assets"] = [str(asset) for asset in asset_files]
            
            return sections

        except Exception as e:
            logger.error(f"Error generating website: {str(e)}")
            raise

    def _parse_response_sections(self, content: str) -> Dict[str, str]:
        """Parse the response into separate HTML, CSS, and JS sections."""
        sections = {
            "html": "",
            "css": "",
            "js": ""
        }
        
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            if line.startswith('```html'):
                current_section = 'html'
                continue
            elif line.startswith('```css'):
                current_section = 'css'
                continue
            elif line.startswith('```javascript'):
                current_section = 'js'
                continue
            elif line.startswith('```'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                    current_content = []
                    current_section = None
                continue
            
            if current_section:
                current_content.append(line)
        
        return sections

    def save_website(self, website_dir: str, sections: Dict[str, str], output_dir = "/generated_website") -> str:
        """Save the generated website files to the specified directory.
        
        Args:
            website_dir: The directory where the original website is stored
            sections: Dictionary containing the generated HTML, CSS, and JS sections
            output_dir: The directory to save the generated website to
            
        Returns:
            str: Path to the generated website directory
        """
        try:
            # Create the output directory
            if output_dir == "":
                output_dir = Path(website_dir) / "generated_website"
            else:
                output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
            
            # Save HTML
            with open(output_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(sections["html"])
            logger.info(f"Saved HTML to: {output_dir / 'index.html'}")
            
            # Save CSS
            with open(output_dir / "styles.css", "w", encoding="utf-8") as f:
                f.write(sections["css"])
            logger.info(f"Saved CSS to: {output_dir / 'styles.css'}")
            
            # Save JavaScript
            with open(output_dir / "script.js", "w", encoding="utf-8") as f:
                f.write(sections["js"])
            logger.info(f"Saved JavaScript to: {output_dir / 'script.js'}")
            
            # Copy all assets
            source_dir = Path(website_dir)
            for asset_path in sections["assets"]:
                asset_path = Path(asset_path)
                if asset_path.exists():
                    # Calculate relative path from source directory
                    rel_path = asset_path.relative_to(source_dir)
                    target_path = output_dir / rel_path
                    
                    # Create parent directories if they don't exist
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(asset_path, target_path)
                    logger.info(f"Copied asset: {asset_path} -> {target_path}")
            
            return str(output_dir)
            
        except Exception as e:
            logger.error(f"Error saving website: {str(e)}")
            raise 