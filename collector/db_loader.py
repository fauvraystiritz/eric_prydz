import json
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def load_tracklists():
    """
    Load tracklists and their tracks into PostgreSQL database.
    
    Database Schema:
    - tracklist table: Stores tracklist URLs and their metadata
      * id: Auto-generated primary key
      * url: The tracklist URL
      * parsed_at: Timestamp when the tracklist was parsed
    
    - track table: Stores individual tracks from each tracklist
      * id: Auto-generated primary key
      * tracklist_id: Foreign key reference to tracklist.id
      * title: Track title
      * artist: Array of artist names
      * played_together: Boolean indicating if played with other tracks
      * is_mashup_element: Boolean indicating if part of a mashup
      * track_number: Unique number for each occurrence of track in a tracklist
      * position: Position in the tracklist (1-based)
    
    Reference Propagation:
    1. When a tracklist is inserted, PostgreSQL generates a unique ID
    2. This ID is returned via RETURNING clause
    3. The ID is then used as tracklist_id for all tracks from that tracklist
    4. This maintains the parent-child relationship between tracklist and tracks
    """
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost')
    )
    cur = conn.cursor()

    # Create schema with tables if they don't exist
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
    
    # Load tracklists from JSON file
    with open('./raw_data/tracklists.json') as f:
        tracklists = json.load(f)
        
    for tracklist in tracklists:
        # Insert tracklist and get its generated ID
        cur.execute(
            """
            INSERT INTO one_thousand_one.tracklist (url, parsed_at)
            VALUES (%s, %s)
            RETURNING id
            """,
            (tracklist['url'], datetime.now())
        )
        tracklist_id = cur.fetchone()[0]
            
        # Enumerate tracks in tracklist and prepare data for batch insertion
        track_values = [
            (
                tracklist_id,  # Link to parent tracklist
                track.get('title', 'Unknown Title'),
                track.get('artist', ['Unknown Artist']),
                track.get('played_together', False),
                track.get('is_mashup_element', False),
                track.get('track_number', None),
                position  # 1-based position in tracklist
            )
            for position, track in enumerate(tracklist['tracks'], 1)
        ]
        
        # Batch insert all tracks for this tracklist
        if track_values:
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
    
    # Commit all changes and clean up
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    load_tracklists()