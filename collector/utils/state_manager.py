import json
from pathlib import Path
from datetime import datetime

class StateManager:
    def __init__(self, state_file='scrape_state.json', output_file='tracklists.json'):
        self.state_file = Path(state_file)
        self.output_file = Path(output_file)
        self.state = self._load_state()
        self.existing_tracklists = self._load_existing_tracklists()
        self.empty_tracklists = self._load_empty_tracklists()

    def _load_empty_tracklists(self):
        return {url for url, data in self.existing_tracklists.items() if not data['tracks']}

    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                state_data = json.load(f)
            # Convert the loaded list back to a set
            state_data['scraped_urls'] = set(state_data['scraped_urls'])
            return state_data
        return {
            'last_run': None,
            'scraped_urls': set(),  # Initialize as a set instead of list
            'total_tracklists': 0
    }

    def _load_existing_tracklists(self):
        if self.output_file.exists():
            with open(self.output_file) as f:
                data = json.load(f)
                return {item['url']: item for item in data}
        return {}

    def is_url_scraped(self, url):
        return url in self.existing_tracklists

    def add_tracklist(self, tracklist_data):
        self.existing_tracklists[tracklist_data['url']] = tracklist_data
        self._save_tracklists()
        self._update_state(tracklist_data['url'])

    def _save_tracklists(self):
        with open(self.output_file, 'w') as f:
            json.dump(list(self.existing_tracklists.values()), f, indent=2)

    def _update_state(self, url):
        self.state['scraped_urls'].add(url)  # Using set's add() method
        self.state['last_run'] = datetime.now().isoformat()
        self.state['total_tracklists'] = len(self.existing_tracklists)
        
        with open(self.state_file, 'w') as f:
            # Convert set to list for JSON serialization
            state_copy = self.state.copy()
            state_copy['scraped_urls'] = list(state_copy['scraped_urls'])
            json.dump(state_copy, f, indent=2)