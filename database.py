import sqlite3
import logging
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for database connections
thread_local = threading.local()

def get_connection():
    """Get thread-specific database connection"""
    if not hasattr(thread_local, 'conn'):
        thread_local.conn = sqlite3.connect("files.db", check_same_thread=False)
        thread_local.conn.row_factory = sqlite3.Row  # Enable dictionary-like access
    return thread_local.conn

def get_cursor():
    """Get thread-specific database cursor"""
    conn = get_connection()
    return conn.cursor()

# Global connection for backward compatibility
conn = get_connection()
cursor = get_cursor()

# Initialize database tables with enhanced schema
def initialize_database():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name TEXT NOT NULL,
        season TEXT DEFAULT '',
        episode TEXT DEFAULT '',
        resolution TEXT DEFAULT '480p',
        file_id TEXT NOT NULL,
        message_id INTEGER NOT NULL,
        file_type TEXT NOT NULL,
        caption TEXT,
        file_size TEXT,
        duration TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(series_name, season, episode, resolution, file_id)
    )
    """)
    
    # Enhanced series_mapping table with timestamps
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS series_mapping (
        hash TEXT PRIMARY KEY,
        series_name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_accessed TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Statistics table for analytics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS download_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name TEXT NOT NULL,
        file_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create indexes for better performance
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_series_resolution ON files(series_name, resolution)",
        "CREATE INDEX IF NOT EXISTS idx_file_id ON files(file_id)",
        "CREATE INDEX IF NOT EXISTS idx_message_id ON files(message_id)",
        "CREATE INDEX IF NOT EXISTS idx_series_season_episode ON files(series_name, season, episode)",
        "CREATE INDEX IF NOT EXISTS idx_download_stats_user ON download_stats(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_download_stats_series ON download_stats(series_name)"
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
        except Exception as e:
            logger.warning(f"Could not create index: {e}")
    
    conn.commit()
    logger.info("Database initialized successfully")

# Backup and maintenance functions
def vacuum_database():
    """Optimize database storage"""
    try:
        cursor.execute("VACUUM")
        conn.commit()
        logger.info("Database vacuum completed")
    except Exception as e:
        logger.error(f"Database vacuum failed: {e}")

def get_database_stats():
    """Get database statistics"""
    stats = {}
    try:
        cursor.execute("SELECT COUNT(*) as total_files FROM files")
        stats['total_files'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT series_name) as total_series FROM files")
        stats['total_series'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) as total_downloads FROM download_stats")
        stats['total_downloads'] = cursor.fetchone()[0]
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
    
    return stats

# Initialize on import
initialize_database()