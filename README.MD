# Eric Prydz Setlist Collector

A tool to collect and analyze Eric Prydz's setlists from 1001tracklists.com.

## Development Setup

This project uses [Rye](https://rye-up.com/) for Python dependency management. Here's how to get started:

# Rye will automatically create a virtual environment and install dependencies
rye sync
```

Use Rye to run Python scripts:

```bash
# Run a specific script
rye run python collector/spiders/tracklists_spider.py

# Or use any other Python command
rye run python -m pytest
```

### 4. Managing Dependencies

```bash
# Add a new dependency
rye add [package-name]

# Add a dev dependency
rye add --dev [package-name]

# Update dependencies
rye sync

# Show installed packages
rye show
```

## Project Structure

- `collector/`: Main package directory
  - `spiders/`: Web scraping spiders
  - `db_loader.py`: Database loading utilities
- `raw_data/`: Collected data storage
  - `tracklists.json`: Raw tracklist data
  - `processed_urls.json`: Tracking of processed URLs