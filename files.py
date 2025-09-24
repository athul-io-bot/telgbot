from pyrogram import filters, enums
from pyrogram.types import Message
from shared import app, ADMINS, DATABASE_CHANNEL
from database import conn, cursor
import datetime
import logging
import re

def parse_file_parameters(text):
    """Parse enhanced file parameters with multiple formats"""
    # Default values
    params = {
        'series_name': '',
        'season': '',
        'episode': '',
        'resolution': '480p',
        'caption': ''
    }
    
    # Try different parsing formats
    patterns = [
        # Format 1: /addfile Series Name | S01E01 | 720p
        r'(.+?)\s*\|\s*([Ss]?\d+[Ee]\d+)\s*\|\s*(\d+p)',
        # Format 2: /addfile Series Name | Season 1 | Episode 1 | 1080p
        r'(.+?)\s*\|\s*[Ss]eason\s*(\d+)\s*\|\s*[Ee]pisode\s*(\d+)\s*\|\s*(\d+p)',
        # Format 3: /addfile Series Name | S01 | E01 | 720p
        r'(.+?)\s*\|\s*([Ss]\d+)\s*\|\s*([Ee]\d+)\s*\|\s*(\d+p)',
        # Format 4: Simple format: /addfile Series Name | Resolution
        r'(.+?)\s*\|\s*(\d+p)',
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if i == 0:  # Format 1: Series | S01E01 | Resolution
                params['series_name'] = match.group(1).strip()
                season_episode = match.group(2).upper()
                # Extract season and episode from S01E01 format
                se_match = re.search(r'S(\d+)E(\d+)', season_episode, re.IGNORECASE)
                if se_match:
                    params['season'] = f"Season {int(se_match.group(1))}"
                    params['episode'] = f"Episode {int(se_match.group(2))}"
                params['resolution'] = match.group(3).strip()
                
            elif i == 1:  # Format 2: Series | Season 1 | Episode 1 | Resolution
                params['series_name'] = match.group(1).strip()
                params['season'] = f"Season {int(match.group(2))}"
                params['episode'] = f"Episode {int(match.group(3))}"
                params['resolution'] = match.group(4).strip()
                
            elif i == 2:  # Format 3: Series | S01 | E01 | Resolution
                params['series_name'] = match.group(1).strip()
                season = re.search(r'\d+', match.group(2)).group()
                episode = re.search(r'\d+', match.group(3)).group()
                params['season'] = f"Season {int(season)}"
                params['episode'] = f"Episode {int(episode)}"
                params['resolution'] = match.group(4).strip()
                
            elif i == 3:  # Format 4: Simple - Series | Resolution
                params['series_name'] = match.group(1).strip()
                params['resolution'] = match.group(2).strip()
            
            return params
    
    # Fallback: simple split by |
    parts = [part.strip() for part in text.split('|')]
    if len(parts) >= 2:
        params['series_name'] = parts[0]
        params['resolution'] = parts[1]
    
    return params

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if not size_bytes:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_duration(media):
    """Get duration for video/audio files"""
    if hasattr(media, 'duration') and media.duration:
        minutes = media.duration // 60
        seconds = media.duration % 60
        return f"{minutes}:{seconds:02d}"
    return ""

@app.on_message(filters.command("addfile") & filters.private)
async def add_file(client, message: Message):
    if message.from_user.id not in ADMINS:
        logging.warning(f"Unauthorized addfile attempt by user {message.from_user.id}")
        await message.reply("❌ You are not authorized to use this command.")
        return

    replied = message.reply_to_message
    if not replied:
        await message.reply("📂 Please reply to a file message to add to a series.")
        return

    try:
        text = message.text.split(" ", 1)[1].strip()
        params = parse_file_parameters(text)
        
        if not params['series_name']:
            await message.reply("❌ Series name is required!")
            return

    except Exception as e:
        logging.error(f"Invalid addfile usage: {e}")
        help_text = """
📘 **Enhanced /addfile Usage:**

**Format 1 (Recommended):**
`/addfile Series Name | S01E01 | 720p`

**Format 2:**
`/addfile Series Name | Season 1 | Episode 1 | 1080p`

**Format 3 (Simple):**
`/addfile Series Name | 480p`

**Examples:**
• `/addfile Breaking Bad | S01E01 | 1080p`
• `/addfile Game of Thrones | Season 1 | Episode 1 | 720p`
• `/addfile Stranger Things | 480p`

📁 *Reply to a file when using this command*
        """
        await message.reply(help_text, parse_mode=enums.ParseMode.MARKDOWN)
        return

    file_id = None
    caption = params['caption']
    file_size = ""
    duration = ""

    # Supported file types with enhanced metadata
    if replied.document:
        file_id = replied.document.file_id
        file_size = format_file_size(replied.document.file_size)
        caption = replied.caption or replied.document.file_name or f"Document - {params['series_name']}"
    elif replied.video:
        file_id = replied.video.file_id
        file_size = format_file_size(replied.video.file_size)
        duration = get_duration(replied.video)
        caption = replied.caption or "Video File"
    elif replied.audio:
        file_id = replied.audio.file_id
        file_size = format_file_size(replied.audio.file_size)
        duration = get_duration(replied.audio)
        caption = replied.caption or replied.audio.title or "Audio File"
    elif replied.animation:
        file_id = replied.animation.file_id
        file_size = format_file_size(replied.animation.file_size)
        caption = replied.caption or "Animation File"
    else:
        await message.reply("❌ Unsupported file type. Supported: document, video, audio, animation.")
        return

    # Build enhanced caption
    enhanced_caption_parts = []
    if params['season'] and params['episode']:
        enhanced_caption_parts.append(f"{params['season']} {params['episode']}")
    elif params['season']:
        enhanced_caption_parts.append(params['season'])
    elif params['episode']:
        enhanced_caption_parts.append(params['episode'])
    
    if duration:
        enhanced_caption_parts.append(f"Duration: {duration}")
    if file_size:
        enhanced_caption_parts.append(f"Size: {file_size}")
    
    enhanced_caption = " • ".join(enhanced_caption_parts) if enhanced_caption_parts else caption

    try:
        # Store the original file_id (don't forward to database channel)
        # This fixes the forwarding issue - we use the original file_id
        original_file_id = file_id
        
        # Insert into database with enhanced fields
        cursor.execute("""
            INSERT INTO files (series_name, season, episode, resolution, file_id, caption, file_size, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            params['series_name'].strip(),
            params['season'],
            params['episode'],
            params['resolution'],
            original_file_id,  # Use original file_id instead of forwarded one
            enhanced_caption,
            file_size,
            duration,
            datetime.datetime.now().isoformat()
        ))
        conn.commit()

        # Success message with details
        success_msg = f"""✅ **File Added Successfully!**

**Series:** {params['series_name']}
**Resolution:** {params['resolution']}"""
        
        if params['season']:
            success_msg += f"\n**Season:** {params['season']}"
        if params['episode']:
            success_msg += f"\n**Episode:** {params['episode']}"
        if file_size:
            success_msg += f"\n**Size:** {file_size}"
        if duration:
            success_msg += f"\n**Duration:** {duration}"

        await message.reply(success_msg, parse_mode=enums.ParseMode.MARKDOWN)
        logging.info(f"File added to series '{params['series_name']}' with resolution '{params['resolution']}' by user {message.from_user.id}")

    except Exception as e:
        logging.error(f"Error adding file: {e}")
        await message.reply(f"⚠️ Error adding file: {str(e)}")

@app.on_message(filters.command("viewfiles") & filters.private)
async def view_files(client, message):
    """Admin command to view files in database"""
    if message.from_user.id not in ADMINS:
        return
    
    try:
        cursor.execute("SELECT series_name, resolution, COUNT(*) FROM files GROUP BY series_name, resolution")
        results = cursor.fetchall()
        
        if not results:
            await message.reply("📭 No files in database yet.")
            return
            
        response = "📊 **Files in Database:**\n\n"
        for series, resolution, count in results:
            response += f"**{series}** - {resolution}: {count} files\n"
            
        await message.reply(response, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
