import scrapy
from pathlib import Path
import json

class TracklistsSpider(scrapy.Spider):
    name = 'prydz_tracklists'
    allowed_domains = ['1001tracklists.com']

    # Add delay settings
    custom_settings = {
        'DOWNLOAD_DELAY': 2,  # 2 second delay between requests
        'RANDOMIZE_DOWNLOAD_DELAY': True,  # Randomize the delay
        'CONCURRENT_REQUESTS': 1,  # Only make one request at a time
        'RETRY_TIMES': 3,  # Retry failed requests up to 3 times
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 400, 403, 404, 408],
        'FEEDS': {
            'raw_data/tracklists.json': {
                'format': 'json',
                'encoding': 'utf8',
                'store_empty': False,
                'overwrite': False,  # Don't overwrite, append instead
                'indent': 2
            },
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_file = Path('raw_data/scrape_state.json')
        self.processed_file = Path('raw_data/processed_urls.json')
        self.urls_to_process = self.load_state()
        self.processed_urls = self.load_processed()
        self.logger.info(f"Loaded {len(self.urls_to_process)} URLs to process")
        self.logger.info(f"Already processed {len(self.processed_urls)} URLs")

    def load_state(self):
        """Load the set of URLs to process."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return set(json.load(f))
        return set()

    def load_processed(self):
        """Load the set of already processed URLs."""
        if self.processed_file.exists():
            with open(self.processed_file) as f:
                return set(json.load(f))
        return set()

    def save_processed(self):
        """Save the set of processed URLs."""
        with open(self.processed_file, 'w') as f:
            json.dump(list(self.processed_urls), f, indent=2)

    def closed(self, reason):
        """Save state when spider closes."""
        self.save_processed()
    
    def errback_httpbin(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
    
    def start_requests(self):
        # Process each URL from our state file that hasn't been processed yet
        urls_remaining = self.urls_to_process - self.processed_urls
        self.logger.info(f"Starting to process {len(urls_remaining)} remaining URLs")
        
        for url in urls_remaining:
            yield scrapy.Request(
                url=url,
                callback=self.parse_tracklist,
                errback=self.errback_httpbin,
                headers=self.get_headers(),
                dont_filter=True
            )

    def parse_tracklist(self, response):
        event_name = response.css('meta[property="og:title"]::attr(content)').get()

        # Add logging for debugging
        self.logger.info(f"Parsing tracklist: {event_name}")
        self.logger.info(f"URL: {response.url}")
        
        tracks = []
        track_numbers = set()
        
        for track_div in response.css('div[id^="tlp"]:not([id$="_content"])'):
            track_number = track_div.attrib.get('id', '').replace('tlp', '')
            track_index = track_div.attrib.get('data-trno', '')
            
            if track_number in track_numbers:
                continue
            track_numbers.add(track_number)
            
            is_mashup_element = 'data-mashpos' in track_div.attrib
            played_together = track_div.css(f'span#tlp{track_index}_tracknumber_value[title="played together with previous track"]::attr(title)').get()
            
            track_data = {
                'title': track_div.css('meta[itemprop="name"]::attr(content)').get(),
                'time': track_div.css('.cueValueField::text').get(),
                'artist': track_div.css('meta[itemprop="byArtist"]::attr(content)').getall(),
                'record_label': track_div.css('meta[itemprop="recordLabel"]::attr(content)').get(),
                'played_together': bool(played_together),
                'is_mashup_element': is_mashup_element,
                'track_number': track_number
            }
            
            track_data = {k: v.strip() if isinstance(v, str) and k not in ['played_together', 'is_mashup_element', 'track_number'] else v 
                         for k, v in track_data.items() if v is not None}
            
            if track_data:
                tracks.append(track_data)

        result = {
            'event': event_name,
            'url': response.url,
            'tracks': tracks
        }
        
        # Mark URL as processed
        self.processed_urls.add(response.url)
        
        self.logger.info(f"Successfully parsed {len(tracks)} tracks from {event_name}")
        yield result

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
