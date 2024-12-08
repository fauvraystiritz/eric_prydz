import asyncio
import json
from pathlib import Path
from typing import Set
import random
import re
import traceback

from playwright.async_api import async_playwright, Page
from tqdm import tqdm


async def scroll_page(page: Page) -> bool:
    """
    Scroll the page in a human-like manner to load more content.
    Returns True if new content was loaded, False if we've reached the end.
    """
    try:
        # Get current scroll position and height
        prev_height = await page.evaluate('document.documentElement.scrollHeight')
        current_position = await page.evaluate('window.pageYOffset')
        
        # Calculate scroll amount (between 300 and 800 pixels)
        scroll_amount = random.randint(300, 800)
        new_position = current_position + scroll_amount
        
        # Scroll to new position with smooth behavior
        await page.evaluate(f'''() => {{
            window.scrollTo({{
                top: {new_position},
                behavior: 'smooth'
            }});
        }}''')
        
        # Wait for scroll to complete and content to load
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Get new height after scrolling
        new_height = await page.evaluate('document.documentElement.scrollHeight')
        
        # Return True if we loaded new content
        return new_height > prev_height
        
    except Exception as e:
        print(f"\nError during scrolling: {e}")
        return False


async def collect_tracklist_urls(proxy: str = None) -> Set[str]:
    """
    Collect all tracklist URLs from Eric Prydz's tracklists page using Playwright.
    Uses browser automation to handle dynamically loaded content with advanced anti-bot measures.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-automation',
                '--no-sandbox'
            ]
        )
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            viewport={'width': 1920, 'height': 1080}
        )
        
        try:
            page = await context.new_page()
            
            print("\nNavigating to Eric Prydz's tracklists page...")
            await page.goto('https://www.1001tracklists.com/dj/ericprydz/index.html', wait_until='networkidle')
            await asyncio.sleep(2)
            
            print("\nWaiting for initial content...")
            await page.wait_for_selector('a[href*="/tracklist/"]', timeout=30000)
            
            # Debug: Check initial page content
            print("\nChecking initial page content...")
            initial_links = await page.query_selector_all('a[href*="/tracklist/"]')
            print(f"Found {len(initial_links)} initial tracklist links")
            
            # Debug: Print a few example URLs
            for link in initial_links[:3]:
                url = await link.get_attribute('href')
                print(f"Example URL: {url}")
            
            urls = set()
            no_new_content_count = 0
            max_no_new_content = 3
            
            print("\nStarting to collect URLs...")
            while no_new_content_count < max_no_new_content:
                # Debug: Print current scroll position and page height
                curr_pos = await page.evaluate('window.pageYOffset')
                page_height = await page.evaluate('document.documentElement.scrollHeight')
                print(f"\nCurrent position: {curr_pos}, Page height: {page_height}")
                
                # Get current URLs with more detailed selector
                new_urls = set()
                links = await page.query_selector_all('a[href*="/tracklist/"]')
                
                for link in links:
                    try:
                        url = await link.get_attribute('href')
                        if url and '/tracklist/' in url:
                            new_urls.add(url)
                    except Exception as e:
                        print(f"Error getting URL from link: {e}")
                
                # Debug: Print found URLs in this pass
                print(f"\nFound {len(new_urls)} URLs in this pass")
                if new_urls:
                    print("Sample URLs found:")
                    for url in list(new_urls)[:2]:
                        print(f"  {url}")
                
                # Check if we found new URLs
                prev_count = len(urls)
                urls.update(new_urls)
                
                if len(urls) > prev_count:
                    print(f"\rFound {len(urls)} total unique tracklist URLs", end='', flush=True)
                    no_new_content_count = 0
                else:
                    print("\nNo new URLs found in this pass")
                    no_new_content_count += 1
                
                # Scroll and wait
                if not await scroll_page(page):
                    print("\nScroll reached end of page")
                    no_new_content_count += 1
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
            
            print(f"\nFinished collecting URLs. Total unique URLs found: {len(urls)}")
            
            # Debug: Save URLs to file
            if urls:
                try:
                    with open('raw_data/tracklist_urls.json', 'w') as f:
                        json.dump(list(urls), f, indent=2)
                    print("\nSuccessfully saved URLs to tracklist_urls.json")
                except Exception as e:
                    print(f"\nError saving URLs to file: {e}")
            
            return urls
            
        except Exception as e:
            print(f"\nError collecting URLs: {e}")
            traceback.print_exc()
            return set()
            
        finally:
            await browser.close()


def save_urls(urls: Set[str], state_file: Path) -> None:
    """Save the collected URLs to the state file."""
    # Load existing state if it exists
    if state_file.exists():
        with open(state_file) as f:
            existing_urls = set(json.load(f))
        urls = urls.union(existing_urls)
    
    # Save updated state
    with open(state_file, 'w') as f:
        json.dump(list(urls), f, indent=2)


def compare_urls(new_urls: Set[str], tracklists_file: Path) -> tuple[set[str], set[str]]:
    """
    Compare newly collected URLs against existing tracklists.json.
    
    Args:
        new_urls: Set of newly collected URLs
        tracklists_file: Path to existing tracklists.json
        
    Returns:
        tuple[set[str], set[str]]: (new_urls, existing_urls)
    """
    if not tracklists_file.exists():
        return new_urls, set()
        
    try:
        with open(tracklists_file) as f:
            content = f.read()
            # Remove any empty arrays at the start
            while content.startswith('[]'):
                content = content.replace('[]', '', 1).strip()
            existing_data = json.loads(content)
    except Exception as e:
        print(f"\nWarning: Error reading tracklists file: {e}")
        print("Proceeding with empty existing tracklists")
        return new_urls, set()
    
    # Extract URLs from existing tracklists
    existing_urls = {
        f"https://www.1001tracklists.com/tracklist/{tl['id']}.html"
        for tl in existing_data
    }
    
    # Find truly new URLs
    truly_new_urls = new_urls - existing_urls
    
    # Print summary
    if truly_new_urls:
        print("\nFound new tracklists:")
        for url in sorted(truly_new_urls):
            # Extract date and venue from URL
            match = re.search(r'/tracklist/[^/]+/eric-prydz-(.+)-(\d{4}-\d{2}-\d{2})\.html', url)
            if match:
                venue, date = match.groups()
                venue = venue.replace('-', ' ').title()
                print(f"- {date}: {venue}")
            else:
                print(f"- {url}")
    else:
        print("\nNo new tracklists found.")
    
    print(f"\nSummary:")
    print(f"- Total URLs collected: {len(new_urls)}")
    print(f"- New tracklists: {len(truly_new_urls)}")
    print(f"- Already in database: {len(new_urls & existing_urls)}")
    
    return truly_new_urls, existing_urls


async def main():
    # Ensure raw_data directory exists
    Path('raw_data').mkdir(exist_ok=True)
    
    # Collect URLs
    urls = await collect_tracklist_urls()  # Remove proxy for now
    
    # Compare against existing tracklists
    tracklists_file = Path('raw_data/tracklists.json')
    new_urls, existing_urls = compare_urls(urls, tracklists_file)
    
    # Save to URLs file
    urls_file = Path('raw_data/tracklist_urls.json')
    save_urls(urls, urls_file)
    print(f"\nSaved all {len(urls)} URLs to {urls_file}")


if __name__ == '__main__':
    asyncio.run(main())
