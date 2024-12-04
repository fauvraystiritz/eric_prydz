import scrapy
from pathlib import Path

class TracklistsSpider(scrapy.Spider):
    name = 'prydz_tracklists'
    allowed_domains = ['1001tracklists.com']
    
    def start_requests(self):
        search_url = 'https://www.1001tracklists.com/dj/ericprydz/index.html'
        
        yield scrapy.Request(
            url=search_url,
            headers=self.get_headers(),
            callback=self.parse_search_results
        )

    def parse_search_results(self, response):
        tracklist_divs = response.css('div.bItm.action.oItm')
        self.logger.info(f"Found {len(tracklist_divs)} tracklist divs")
        
        for div in tracklist_divs[:100]:  # Removed the [:2] limit since it's working well
            onclick = div.attrib.get('onclick', '')
            url_match = onclick.split("'")[1] if "'" in onclick else None
            
            if url_match:
                full_url = f'https://www.1001tracklists.com{url_match}'
                title = div.css('div.bTitle a::text').get()
                self.logger.info(f"Processing tracklist: {title}")
                
                yield scrapy.Request(
                    url=full_url,
                    callback=self.parse_tracklist,
                    headers=self.get_headers()
                )

    def parse_tracklist(self, response):
        event_name = response.css('meta[property="og:title"]::attr(content)').get()
        
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

        yield {
            'event': event_name,
            'url': response.url,
            'tracks': tracks
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }