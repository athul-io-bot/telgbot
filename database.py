import sqlite3
import logging
from pathlib import Path
import threading
import atexit

logger = logging.getLogger(__name__)

# Database connection
DB_FILE = Path(__file__).parent.joinpath('data', 'files.db')
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

# Thread-safe database connection
_thread_local = threading.local()

def get_connection():
    """Get thread-local database connection"""
    if not hasattr(_thread_local, 'connection'):
        _thread_local.connection = sqlite3.connect(
            str(DB_FILE), 
            check_same_thread=False,
            timeout=30.0
        )
        # Enable WAL mode for better concurrent access
        _thread_local.connection.execute("PRAGMA journal_mode=WAL")
        _thread_local.connection.execute("PRAGMA synchronous=NORMAL")
        _thread_local.connection.execute("PRAGMA cache_size=10000")
        _thread_local.connection.execute("PRAGMA temp_store=memory")
    return _thread_local.connection

def get_cursor():
    """Get cursor from thread-local connection"""
    return get_connection().cursor()

# Global connection and cursor for backward compatibility
conn = get_connection()
cursor = get_cursor()

def initialize_database():
    """Initialize database with required tables"""
    try:
        local_conn = get_connection()
        local_cursor = local_conn.cursor()
        
        # Files table
        local_cursor.execute("""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Series mapping for callback data
        local_cursor.execute("""
            CREATE TABLE IF NOT EXISTS series_mapping (
                hash TEXT PRIMARY KEY,
                series_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Download statistics
        local_cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                series_name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Schema version table
        local_cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            )
        """)
        
        # Create indexes for better performance
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_series ON files(series_name)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_resolution ON files(series_name, resolution)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON files(message_id)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_id ON files(file_id)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON series_mapping(hash)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_downloads ON download_stats(user_id)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_series ON download_stats(series_name)")
        local_cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_time ON download_stats(downloaded_at)")
        
        local_conn.commit()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def get_schema_version():
    """Get current schema version"""
    try:
        local_conn = get_connection()
        local_cursor = local_conn.cursor()
        
        local_cursor.execute("SELECT version FROM schema_version WHERE id = 1")
        row = local_cursor.fetchone()
        if row:
            return int(row[0])
        else:
            local_cursor.execute("INSERT INTO schema_version (id, version) VALUES (1, 1)")
            local_conn.commit()
            return 1
    except Exception as e:
        logger.error(f"Error getting schema version: {e}")
        return 1

def set_schema_version(v):
    """Set schema version"""
    try:
        local_conn = get_connection()
        local_cursor = local_conn.cursor()
        local_cursor.execute("INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, ?)", (int(v),))
        local_conn.commit()
    except Exception as e:
        logger.error(f"Error setting schema version: {e}")

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """Execute a database query with proper error handling"""
    try:
        local_conn = get_connection()
        local_cursor = local_conn.cursor()
        
        if params:
            local_cursor.execute(query, params)
        else:
            local_cursor.execute(query)
            
        if fetch_one:
            return local_cursor.fetchone()
        elif fetch_all:
            return local_cursor.fetchall()
        
        local_conn.commit()
        return local_cursor.rowcount
        
    except Exception as e:
        logger.error(f"Database query error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        raise

def close_connections():
    """Close all database connections"""
    try:
        if hasattr(_thread_local, 'connection'):
            _thread_local.connection.close()
            delattr(_thread_local, 'connection')
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

# Register cleanup function
atexit.register(close_connections)

# Perform schema migrations
CURRENT_SCHEMA_VERSION = 1
try:
    current_version = get_schema_version()

    if current_version < CURRENT_SCHEMA_VERSION:
        logger.info(f"Migrating database from version {current_version} to {CURRENT_SCHEMA_VERSION}")
        # Add future migration steps here when needed
        set_schema_version(CURRENT_SCHEMA_VERSION)

    # Initialize database on import
    initialize_database()
    
except Exception as e:
    logger.error(f"Database setup failed: {e}")
    raise