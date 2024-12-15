import asyncio
import json
from pathlib import Path
from typing import Set
import random
import re
import traceback
import sys

from playwright.async_api import async_playwright, Page
from tqdm import tqdm


async def scroll_up_and_collect(page: Page) -> Set[str]:
    """
    Scroll up from bottom of page while collecting URLs.
    Returns set of collected URLs.
    """
    collected_urls = set()
    try:
        print("\nStarting upward scrolling and URL collection...")
        for i in range(10):  
            print(f"Scroll attempt {i+1}/10")
            
            # Collect URLs at current position
            try:
                new_urls = set()
                links = await page.query_selector_all('a[href*="/tracklist/"]')
                for link in links:
                    url = await link.get_attribute('href')
                    if url and '/tracklist/' in url:
                        if url not in collected_urls:
                            new_urls.add(url)
                
                collected_urls.update(new_urls)
                print(f"Total unique URLs collected so far: {len(collected_urls)}")
                if new_urls:
                    print(f"New URLs found in this scroll ({len(new_urls)}):")
                    for url in list(new_urls)[:2]:
                        print(f"  {url}")
            except Exception as e:
                print(f"Error collecting URLs: {e}")
            
            # Get current scroll position
            prev_pos = await page.evaluate('window.pageYOffset')
            
            # Random mouse movement
            await page.mouse.move(
                random.randint(100, 800),
                random.randint(100, 600)
            )
            
            # Random delay before scroll (0.5 to 2 seconds)
            await asyncio.sleep(random.uniform(0.5, 2))
            
            # Scroll upward with natural easing
            await page.evaluate('''() => {
                function easeInOutQuad(t) {
                    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
                }
                
                const scrollAmount = -(Math.floor(Math.random() * 800) + 300);  // Random between -300 and -1100px
                const duration = 1000;
                const start = window.pageYOffset;
                const startTime = performance.now();
                
                function scroll() {
                    const currentTime = performance.now();
                    const time = Math.min(1, (currentTime - startTime) / duration);
                    
                    window.scrollTo(0, start + (scrollAmount * easeInOutQuad(time)));
                    
                    if (time < 1) {
                        requestAnimationFrame(scroll);
                    }
                }
                
                scroll();
            }''')
            
            # Random pause after scroll (1 to 3 seconds)
            await asyncio.sleep(random.uniform(1, 3))
            
            # Add longer pause every 5 scrolls
            if (i + 1) % 5 == 0:
                print("Taking a short break...")
                await asyncio.sleep(random.uniform(3, 6))
            
            # Get current position for logging
            curr_pos = await page.evaluate('window.pageYOffset')
            print(f"Current scroll position: {curr_pos}px")
            
            # If we've reached the top, we can stop
            if curr_pos <= 0:
                print("Reached the top of the page")
                break
        
        print("\nCompleted scrolling and collection sequence")
        return collected_urls
            
    except Exception as e:
        print(f"\nError during scrolling and collection: {e}")
        traceback.print_exc()
        return collected_urls


async def wait_for_user_input():
    """Wait for user input in an async-friendly way."""
    print("\nManual scrolling mode activated!")
    print("Please manually scroll to the bottom of the page.")
    print("Once you've reached the bottom and solved any CAPTCHA, press Enter to begin collection...")
    return await asyncio.get_event_loop().run_in_executor(None, input)


def save_urls_to_file(urls: Set[str]) -> None:
    """Save URLs to JSON file."""
    urls_list = sorted(list(urls))  # Convert to sorted list for consistent ordering
    urls_file = Path('raw_data/tracklist_urls.json')
    
    # Ensure directory exists
    urls_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save URLs
    with urls_file.open('w', encoding='utf-8') as f:
        json.dump(urls_list, f, indent=2)


async def main():
    print("Starting URL collector...", flush=True)
    try:
        async with async_playwright() as p:
            print("Launching browser...", flush=True)
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
            
            page = await context.new_page()
            
            print("Navigating to Eric Prydz's tracklists page...", flush=True)
            # Navigate to the page
            await page.goto('https://www.1001tracklists.com/dj/ericprydz/index.html', wait_until='networkidle')
            await asyncio.sleep(2)
            
            print("\nManual scrolling mode activated!", flush=True)
            print("Please manually scroll to the bottom of the page.", flush=True)
            print("Once you've reached the bottom and solved any CAPTCHA, press Enter to begin collection...", flush=True)
            sys.stdout.flush()
            await asyncio.get_event_loop().run_in_executor(None, input)
            
            # Collect URLs while scrolling up
            collected_urls = await scroll_up_and_collect(page)
            
            # Save the collected URLs
            if collected_urls:
                print(f"\nSaving {len(collected_urls)} unique tracklist URLs...")
                save_urls_to_file(collected_urls)
                print("URLs saved successfully!")
            else:
                print("\nNo URLs were collected!")
            
            await browser.close()
            
    except Exception as e:
        print(f"Error in main: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
