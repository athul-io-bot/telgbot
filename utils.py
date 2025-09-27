import hashlib
import base64
import sqlite3
from database import cursor, conn
import logging

logger = logging.getLogger(__name__)

def encode_series_name(series_name):
    """Generate a simple hash for series name"""
    import hashlib
    return hashlib.md5(series_name.encode('utf-8')).hexdigest()[:12]

def decode_series_name(encoded_hash):
    """Get series name from hash"""
    try:
        logger.debug(f"Attempting to decode hash: '{encoded_hash}'")
        
        cursor.execute("SELECT series_name FROM series_mapping WHERE hash = ?", (encoded_hash,))
        result = cursor.fetchone()
        
        if result:
            series_name = result[0]
            logger.debug(f"Successfully decoded '{encoded_hash}' -> '{series_name}'")
            return series_name
        else:
            logger.warning(f"No series found for hash: '{encoded_hash}'")
            return "Unknown Series"
            
    except Exception as e:
        logger.error(f"Error decoding series name from hash '{encoded_hash}': {e}")
        return "Unknown Series"
def store_series_mapping(series_name, encoded_hash):
    """Store series name and hash mapping"""
    try:
        # Remove padding for consistent storage
        clean_hash = encoded_hash.rstrip('=')
        cursor.execute(
            "INSERT OR REPLACE INTO series_mapping (hash, series_name) VALUES (?, ?)",
            (clean_hash, series_name)
        )
        conn.commit()
        logger.debug(f"Stored mapping: {series_name} -> {clean_hash}")
    except Exception as e:
        logger.error(f"Error storing series mapping '{series_name}': {e}")

def log_download(user_id, series_name, file_id):
    """Log file downloads for statistics"""
    try:
        cursor.execute(
            "INSERT INTO download_stats (user_id, series_name, file_id) VALUES (?, ?, ?)",
            (user_id, series_name, file_id)
        )
        conn.commit()
        logger.debug(f"Logged download: user {user_id}, series {series_name}")
    except Exception as e:
        logger.error(f"Error logging download for user {user_id}: {e}")

def get_series_stats(series_name=None):
    """Get download statistics for a series or all series"""
    try:
        if series_name:
            cursor.execute(
                "SELECT COUNT(*) FROM download_stats WHERE series_name = ?",
                (series_name,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM download_stats")
        
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting series stats: {e}")
        return 0

def cleanup_old_mappings():
    """Remove mappings for series that no longer exist"""
    try:
        cursor.execute("""
            DELETE FROM series_mapping 
            WHERE series_name NOT IN (SELECT DISTINCT series_name FROM files)
        """)
        deleted_count = cursor.rowcount
        conn.commit()
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} orphaned series mappings")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up mappings: {e}")
        return 0

def validate_series_exists(series_name):
    """Check if a series has files in the database"""
    try:
        cursor.execute("SELECT COUNT(*) FROM files WHERE series_name = ?", (series_name,))
        result = cursor.fetchone()
        return result[0] > 0 if result else False
    except Exception as e:
        logger.error(f"Error validating series '{series_name}': {e}")
        return False

def get_all_series():
    """Get all series with file counts"""
    try:
        cursor.execute("""
            SELECT series_name, COUNT(*) as file_count, 
                   COUNT(DISTINCT resolution) as resolution_count
            FROM files 
            GROUP BY series_name 
            ORDER BY series_name
        """)
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting all series: {e}")
        return []