import hashlib
from database import cursor, conn

def encode_series_name(series_name):
    """Generate a short hash for the series name and store mapping in database"""
    # Create a short hash from the series name
    hash_object = hashlib.md5(series_name.encode())
    short_hash = hash_object.hexdigest()[:12]  # Use first 12 characters
    
    # Store or update the mapping in database
    cursor.execute("INSERT OR REPLACE INTO series_mapping (hash, series_name) VALUES (?, ?)", 
                   (short_hash, series_name))
    conn.commit()
    
    return short_hash

def decode_series_name(encoded_hash):
    """Retrieve the original series name from the hash"""
    cursor.execute("SELECT series_name FROM series_mapping WHERE hash = ?", (encoded_hash,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return "Unknown Series"  # Fallback if hash not found
