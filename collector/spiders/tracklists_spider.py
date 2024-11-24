import scrapy

class TracklistsSpider(scrapy.Spider):
    name = 'prydz_tracklists'
    start_urls = [
        'https://www.1001tracklists.com/tracklist/2szbt321/eric-prydz-tsunami-stage-seismic-dance-event-united-states-2024-11-17.html'
    ]

    def parse(self, response):
        event_name = response.css('meta[property="og:title"]::attr(content)').get()
        
        tracks = []
        track_numbers = set()
        
        for track_div in response.css('div[id^="tlp"]:not([id$="_content"])'):
            track_number = track_div.attrib.get('id', '').replace('tlp', '')
            track_index = track_div.attrib.get('data-trno', '')
            
            if track_number in track_numbers:
                continue
            track_numbers.add(track_number)
            
            # Check if this is a component track using data-mashpos attribute
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
            
            # Debug print
            print(f"\nTrack {track_index}:")
            print(f"Title: {track_data['title']}")
            print(f"Is component: {is_mashup_element}")
            print(f"Attributes: {track_div.attrib}")
            
            # Clean up the data
            track_data = {k: v.strip() if isinstance(v, str) and k not in ['played_together', 'is_mashup_element', 'track_number'] else v 
                         for k, v in track_data.items() if v is not None}
            
            if track_data:
                tracks.append(track_data)

        yield {
            'event': event_name,
            'url': response.url,
            'tracks': tracks
        }

    def start_requests(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        for url in self.start_urls:
            yield scrapy.Request(url=url, headers=headers, callback=self.parse)