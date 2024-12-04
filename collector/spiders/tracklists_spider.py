import scrapy
from pathlib import Path

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
    }

    def errback_httpbin(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
    
    def start_requests(self):
        search_url = 'https://www.1001tracklists.com/dj/ericprydz/index.html'
        
        yield scrapy.Request(
            url=search_url,
            headers=self.get_headers(),
            callback=self.parse_search_results,
            errback=self.errback_httpbin,
            dont_filter=True
        )

    def parse_search_results(self, response):
        # First, let's debug what we're getting
        self.logger.info(f"Response status: {response.status}")
        self.logger.info(f"Response URL: {response.url}")
    
        # Let's see what HTML we're getting
        with open('debug.html', 'w') as f:
            f.write(response.text)

        tracklist_divs = response.css('div.bItm.action.oItm')
        self.logger.info(f"Found {len(tracklist_divs)} tracklist divs")

        # Debug the HTML structure
        self.logger.info(f"First 500 chars of response: {response.text[:500]}")
        
        for div in tracklist_divs[:50]:  # Removed the [:2] limit since it's working well
            onclick = div.attrib.get('onclick', '')
            url_match = onclick.split("'")[1] if "'" in onclick else None
            
            if url_match:
                full_url = f'https://www.1001tracklists.com{url_match}'
                title = div.css('div.bTitle a::text').get()
                self.logger.info(f"Processing tracklist: {title}")
                
                yield scrapy.Request(
                    url=full_url,
                    callback=self.parse_tracklist,
                    errback=self.errback_httpbin,
                    headers=self.get_headers(),
                    dont_filter=True,
                    meta={'title': title}
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