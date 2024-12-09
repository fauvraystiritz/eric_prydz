import json
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def load_tracklists():
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost')
    )
    cur = conn.cursor()

    # Create tables if they don't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS one_thousand_one.tracklist (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            url TEXT NOT NULL,
            parsed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS one_thousand_one.track (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tracklist_id INTEGER REFERENCES one_thousand_one.tracklist(id),
            title TEXT NOT NULL,
            artist TEXT[] NOT NULL,
            played_together BOOLEAN NOT NULL,
            is_mashup_element BOOLEAN NOT NULL,
            track_number TEXT,
            position INTEGER NOT NULL
        );
    """)
    
    # Find all tracklist JSON files in raw_data directory
    data_files = Path('./raw_data').glob('tracklists*.json')
    
    for file_path in data_files:
        print(f"Processing {file_path}...")
        with open(file_path) as f:
            tracklists = json.load(f)
            
        for tracklist in tracklists:
            # Get parsed_at or use current timestamp
            parsed_at = tracklist.get('parsed_at', datetime.now().isoformat())

            # Insert tracklist
            cur.execute(
                """
                INSERT INTO one_thousand_one.tracklist (url, parsed_at)
                VALUES (%s, %s)
                RETURNING id
                """,
                (tracklist['url'], datetime.now())
            )
            tracklist_id = cur.fetchone()[0]
                
            # Prepare track data for insertion
            track_values = [
                (
                    tracklist_id,
                    track.get('title', 'Unknown Title'),
                    track.get('artist', ['Unknown Artist']),
                    track.get('played_together', False),
                    track.get('is_mashup_element', False),
                    track.get('track_number', None),
                    position
                )
                for position, track in enumerate(tracklist['tracks'], 1)
            ]
            
            # Only insert if we have tracks
            if track_values:
                # Bulk insert tracks
                execute_values(
                    cur,
                    """
                    INSERT INTO one_thousand_one.track 
                        (tracklist_id, title, artist, played_together, 
                         is_mashup_element, track_number, position)
                    VALUES %s
                    """,
                    track_values
                )
    
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    load_tracklists()