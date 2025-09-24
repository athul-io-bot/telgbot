import sqlite3

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
        episode_name TEXT,
        resolution TEXT,
        file_id TEXT,
        caption TEXT,
        file_size TEXT,
        duration TEXT,
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
    
    conn.commit()

# Initialize on import
initialize_database()
