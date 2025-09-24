import sqlite3
import logging

logger = logging.getLogger(__name__)

# Single database connection for the entire application
conn = sqlite3.connect("files.db", check_same_thread=False)
cursor = conn.cursor()

# Initialize database tables
def initialize_database():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name TEXT,
        season TEXT,
        episode TEXT,
        resolution TEXT,
        file_id TEXT UNIQUE,  -- Added UNIQUE constraint
        caption TEXT,
        file_size TEXT,
        duration TEXT,
        message_id INTEGER,  -- Store message ID for easier retrieval
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Add series_mapping table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS series_mapping (
        hash TEXT PRIMARY KEY,
        series_name TEXT
    )
    """)
    
    # Create index for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_resolution ON files(series_name, resolution)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_id ON files(file_id)")
    
    conn.commit()
    logger.info("Database initialized successfully")

# Initialize on import
initialize_database()
