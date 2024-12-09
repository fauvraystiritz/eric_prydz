#!/usr/bin/env python3

import asyncio
import json
from pathlib import Path
import random
from typing import Dict, List, Optional, Set
from datetime import datetime

from playwright.async_api import async_playwright, Page
from tqdm import tqdm

class TracklistsSpider:
    """Spider to parse tracklist pages from 1001tracklists.com"""
    
    def __init__(self):
        # Ensure raw_data directory exists
        Path('raw_data').mkdir(exist_ok=True)
        
        self.urls_file = Path('raw_data/tracklist_urls.json')
        self.processed_file = Path('raw_data/processed_urls.json')
        self.output_file = Path('raw_data/tracklists.json')
        
        # Initialize state files if they don't exist
        if not self.processed_file.exists():
            with open(self.processed_file, 'w') as f:
                json.dump([], f)
        if not self.output_file.exists():
            with open(self.output_file, 'w') as f:
                json.dump([], f)
                
        self.processed_urls = self.load_processed()
        print(f"Already processed {len(self.processed_urls)} URLs")
    
    def load_processed(self) -> Set[str]:
        """Load the set of already processed URLs."""
        if self.processed_file.exists():
            with open(self.processed_file) as f:
                return set(json.load(f))
        return set()
    
    def save_processed(self):
        """Save the set of processed URLs."""
        with open(self.processed_file, 'w') as f:
            json.dump(list(self.processed_urls), f, indent=2)
    
    def load_existing_tracklists(self) -> List[Dict]:
        """Load existing tracklists from the output file."""
        if self.output_file.exists():
            try:
                with open(self.output_file) as f:
                    existing = json.load(f)
                print(f"\nLoaded {len(existing)} existing tracklists")
                return existing
            except json.JSONDecodeError:
                print("\nWarning: Could not parse existing tracklists.json, starting fresh")
                return []
            except Exception as e:
                print(f"\nError loading existing tracklists: {e}")
                return []
        return []
    
    def save_tracklist(self, tracklist: Dict):
        """Append a tracklist to the output file."""
        try:
            # Load existing tracklists
            tracklists = self.load_existing_tracklists()
            
            # Check if this URL is already in the tracklists
            existing_urls = {t['url'] for t in tracklists}
            if tracklist['url'] in existing_urls:
                print(f"\nSkipping already parsed tracklist: {tracklist['url']}")
                return
            
            # Append new tracklist
            tracklists.append(tracklist)
            
            # Save back to file
            with open(self.output_file, 'w') as f:
                json.dump(tracklists, f, indent=2)
            print(f"\nSaved new tracklist: {tracklist['url']}")
            print(f"Total tracklists saved: {len(tracklists)}")
            
        except Exception as e:
            print(f"\nError saving tracklist: {e}")
            import traceback
            traceback.print_exc()
    
    async def check_for_captcha(self, page: Page) -> bool:
        """Check if we've hit a CAPTCHA page."""
        try:
            # Common CAPTCHA indicators
            captcha_elements = await page.query_selector_all([
                'iframe[src*="captcha"]',
                'iframe[src*="recaptcha"]',
                'div.g-recaptcha',
                '#captcha',
                '[class*="captcha"]'
            ])
            return len(captcha_elements) > 0
        except Exception:
            return False

    async def wait_for_captcha(self, page: Page):
        """Wait for user to solve CAPTCHA."""
        print("\n⚠️  CAPTCHA detected! Please:")
        print("1. Solve the CAPTCHA in the browser window")
        print("2. Wait for the page to load")
        print("3. Press Enter in this terminal to continue...")
        
        try:
            input()
        except EOFError:
            # If we can't get input, wait a reasonable time
            print("Running in non-interactive mode, waiting 30 seconds...")
            await asyncio.sleep(30)
        
        # Wait for navigation to complete after CAPTCHA
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            pass

    async def wait_for_page_load(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Wait for page to load with retries and fallbacks."""
        for attempt in range(max_retries):
            try:
                # First try with networkidle
                await page.goto(url, wait_until='networkidle', timeout=60000)
                return True
            except Exception as e:
                print(f"\nTimeout on attempt {attempt + 1}/{max_retries} with networkidle")
                try:
                    # Fallback to domcontentloaded
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait a bit for additional content
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    
                    return True
                except Exception as e:
                    print(f"Fallback also failed: {e}")
                    if attempt == max_retries - 1:
                        print("All retries failed")
                        return False
                    print("Retrying after delay...")
                    await asyncio.sleep(5)
        return False

    async def parse_tracklist(self, page: Page, url: str) -> Optional[Dict]:
        """Parse a single tracklist page."""
        try:
            print(f"\nParsing: {url}")
            
            # Try to load the page
            if not await self.wait_for_page_load(page, url):
                print("Failed to load page after retries")
                return None
            
            # Check for CAPTCHA
            if await self.check_for_captcha(page):
                await self.wait_for_captcha(page)
                
                # Reload page after CAPTCHA if needed
                if not await self.wait_for_page_load(page, url):
                    print("Failed to load page after CAPTCHA")
                    return None
            
            # Get page title
            title = await page.title()
            print(f"Page title: {title}")
            
            # Debug: Print page title
            print(f"Page title: {await page.title()}")
            
            # Get event name from meta tag
            event_name = None
            title_meta = await page.query_selector('meta[property="og:title"]')
            if title_meta:
                event_name = await title_meta.get_attribute('content')
                print(f"Found event: {event_name}")
            else:
                print("Warning: Could not find event name meta tag")
                # Try alternate method
                title_el = await page.query_selector('.tracklistTitle')
                if title_el:
                    event_name = await title_el.inner_text()
                    print(f"Found event from title element: {event_name}")
            
            if not event_name:
                print("Error: Could not find event name")
                return None
            
            tracks = []
            track_numbers = set()
            
            # Find all track divs
            track_divs = await page.query_selector_all('div[id^="tlp"]:not([id$="_content"])')
            print(f"Found {len(track_divs)} potential track divs")
            
            for track_div in track_divs:
                try:
                    # Get track number and index
                    track_number = await track_div.get_attribute('id')
                    if track_number:
                        track_number = track_number.replace('tlp', '')
                        print(f"\nProcessing track number: {track_number}")
                    else:
                        print("Warning: Track div has no ID")
                        continue
                    
                    track_index = await track_div.get_attribute('data-trno')
                    print(f"Track index: {track_index}")
                    
                    if track_number in track_numbers:
                        print(f"Skipping duplicate track number: {track_number}")
                        continue
                    track_numbers.add(track_number)
                    
                    # Check for mashup and played together
                    is_mashup = await track_div.get_attribute('data-mashpos') is not None
                    played_together_el = await page.query_selector(f'span#tlp{track_index}_tracknumber_value[title="played together with previous track"]')
                    played_together = played_together_el is not None
                    
                    # Get track metadata with error handling
                    title = None
                    title_meta = await track_div.query_selector('meta[itemprop="name"]')
                    if title_meta:
                        title = await title_meta.get_attribute('content')
                    
                    time = None
                    time_el = await track_div.query_selector('.cueValueField')
                    if time_el:
                        time = await time_el.inner_text()
                    
                    artists = []
                    artist_metas = await track_div.query_selector_all('meta[itemprop="byArtist"]')
                    for artist_meta in artist_metas:
                        artist = await artist_meta.get_attribute('content')
                        if artist:
                            artists.append(artist)
                    
                    label = None
                    label_meta = await track_div.query_selector('meta[itemprop="recordLabel"]')
                    if label_meta:
                        label = await label_meta.get_attribute('content')
                    
                    print(f"Found track: {title} by {artists}")
                    
                    track_data = {
                        'title': title.strip() if title else None,
                        'time': time.strip() if time else None,
                        'artist': artists,
                        'record_label': label.strip() if label else None,
                        'played_together': played_together,
                        'is_mashup_element': is_mashup,
                        'track_number': track_number
                    }
                    
                    # Clean up None values and strip strings
                    track_data = {k: v for k, v in track_data.items() if v is not None}
                    
                    if track_data:
                        tracks.append(track_data)
                        print(f"Added track: {track_data}")
                    else:
                        print("Warning: Empty track data")
                        
                except Exception as e:
                    print(f"Error parsing track: {e}")
                    continue
            
            if not tracks:
                print("Error: No tracks found")
                return None
            
            result = {
                'event': event_name,
                'url': url,
                'tracks': tracks,
                'parsed_at': datetime.now().isoformat()
            }
            
            print(f"Successfully parsed {len(tracks)} tracks")
            return result
            
        except Exception as e:
            print(f"Error parsing tracklist {url}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def run(self):
        """Run the spider to parse all tracklists"""
        try:
            # Load URLs
            if not self.urls_file.exists():
                print("No URLs file found at", self.urls_file)
                return
                
            with open(self.urls_file, 'r') as f:
                relative_urls = json.load(f)
            
            # Convert relative URLs to absolute URLs
            urls = [f"https://www.1001tracklists.com{url}" for url in relative_urls]
            
            # Filter out already processed URLs
            urls_remaining = [url for url in urls if url not in self.processed_urls]
            print(f"\nLoaded {len(urls_remaining)} URLs to parse")
            
            if not urls_remaining:
                print("No new URLs to process")
                return
            
            print("\n⚠️  Important: When you see a CAPTCHA:")
            print("1. Solve it in the browser window")
            print("2. Wait for the page to load")
            print("3. Press Enter in this terminal to continue")
            print("\nStarting in 5 seconds...")
            await asyncio.sleep(5)
            
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
                
                page = await context.new_page()
                
                # Process each URL with progress bar
                with tqdm(total=len(urls_remaining), desc="Parsing tracklists") as pbar:
                    for url in urls_remaining:
                        try:
                            # Parse tracklist
                            tracklist = await self.parse_tracklist(page, url)
                            
                            if tracklist:
                                # Save parsed tracklist
                                self.save_tracklist(tracklist)
                                self.processed_urls.add(url)
                                self.save_processed()
                                print(f"\nSaved tracklist: {url}")
                            else:
                                print(f"\nFailed to parse: {url}")
                            
                            pbar.update(1)
                            
                            # Rate limiting - randomize more to seem human-like
                            await asyncio.sleep(random.uniform(5.0, 10.0))
                            
                        except Exception as e:
                            print(f"\nError processing {url}: {e}")
                            continue
                
                await browser.close()
                
        except Exception as e:
            print(f"Error running spider: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.save_processed()

async def main():
    spider = TracklistsSpider()
    await spider.run()

if __name__ == '__main__':
    asyncio.run(main())
