import hashlib
import base64
from database import cursor, conn

def encode_series_name(series_name):
    """Generate a short hash for the series name using SHA256 and store mapping in database"""
    # Create a secure hash from the series name
    hash_object = hashlib.sha256(series_name.encode())
    hash_bytes = hash_object.digest()
    
    # Use base64 encoding for shorter, URL-safe hash
    short_hash = base64.urlsafe_b64encode(hash_bytes[:9]).decode('utf-8')  # 12 chars
    
    # Store or update the mapping in database
    cursor.execute("INSERT OR REPLACE INTO series_mapping (hash, series_name) VALUES (?, ?)", 
                   (short_hash, series_name))
    conn.commit()
    
    return short_hash

def decode_series_name(encoded_hash):
    """Retrieve the original series name from the hash"""
    try:
        cursor.execute("SELECT series_name FROM series_mapping WHERE hash = ?", (encoded_hash,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return "Unknown Series"  # Fallback if hash not found
    except Exception:
        return "Unknown Series"

def sanitize_callback_data(text):
    """Sanitize text for use in callback data"""
    # Replace problematic characters
    return text.replace('|', '_').replace(':', '_').replace(' ', '-')

def desanitize_callback_data(text):
    """Convert sanitized callback data back to readable text"""
    return text.replace('_', '|').replace('-', ' ')