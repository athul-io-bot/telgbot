from pyrogram import filters, enums
from pyrogram.types import Message
from shared import app, ADMINS, DATABASE_CHANNEL
from database import conn, cursor
from utils import encode_series_name, store_series_mapping
import datetime
import logging
import re

logger = logging.getLogger(__name__)

def parse_addfile_command(text):
    """
    Parse /addfile command with multiple supported formats:
    1. /addfile Series Name | S01E01 | 720p
    2. /addfile Series Name | Season 1 | Episode 1 | 1080p  
    3. /addfile Series Name | 480p
    """
    text = text.strip()
    patterns = [
        r'^(.+?)\s*\|\s*([Ss]\d+[Ee]\d+)\s*\|\s*(\d+p)$',
        r'^(.+?)\s*\|\s*[Ss]eason\s*(\d+)\s*\|\s*[Ee]pisode\s*(\d+)\s*\|\s*(\d+p)$',
        r'^(.+?)\s*\|\s*(\d+p)$'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 3:  # Format 1: Series | S01E01 | Resolution
                series_name, ep_code, resolution = groups
                # Extract season and episode from S01E01
                ep_match = re.match(r'[Ss](\d+)[Ee](\d+)', ep_code)
                if ep_match:
                    season = f"S{int(ep_match.group(1)):02d}"
                    episode = f"E{int(ep_match.group(2)):02d}"
                    return series_name.strip(), season, episode, resolution
            elif len(groups) == 4:  # Format 2: Series | Season 1 | Episode 1 | Resolution
                series_name, season_num, ep_num, resolution = groups
                return series_name.strip(), f"S{int(season_num):02d}", f"E{int(ep_num):02d}", resolution
            elif len(groups) == 2:  # Format 3: Series | Resolution
                series_name, resolution = groups
                return series_name.strip(), "", "", resolution
    
    # Fallback: simple split
    parts = [p.strip() for p in text.split('|')]
    if len(parts) >= 2:
        return parts[0], "", "", parts[1]
    
    return None

def get_file_info(replied_message):
    """Extract file information from replied message"""
    if replied_message.document:
        file_type = "document"
        file_id = replied_message.document.file_id
        file_size = replied_message.document.file_size
        file_name = replied_message.document.file_name or "Document"
        duration = None
    elif replied_message.video:
        file_type = "video"
        file_id = replied_message.video.file_id
        file_size = replied_message.video.file_size
        file_name = getattr(replied_message.video, 'file_name', None) or "Video"
        duration = getattr(replied_message.video, 'duration', None)
    elif replied_message.audio:
        file_type = "audio"
        file_id = replied_message.audio.file_id
        file_size = replied_message.audio.file_size
        file_name = replied_message.audio.title or replied_message.audio.file_name or "Audio"
        duration = getattr(replied_message.audio, 'duration', None)
    elif replied_message.animation:
        file_type = "animation"
        file_id = replied_message.animation.file_id
        file_size = replied_message.animation.file_size
        file_name = getattr(replied_message.animation, 'file_name', None) or "Animation"
        duration = getattr(replied_message.animation, 'duration', None)
    else:
        return None
    
    return {
        'type': file_type,
        'id': file_id,
        'size': file_size,
        'name': file_name,
        'duration': duration
    }

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if not size_bytes:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def format_duration(seconds):
    """Format duration in seconds to MM:SS"""
    if not seconds:
        return ""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

@app.on_message(filters.command("addfile") & filters.private)
async def add_file_handler(client, message: Message):
    """Admin command to add files to series"""
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.reply("Access denied. Admin only command.")
        return

    if not message.reply_to_message:
        await message.reply(
            "Usage: Reply to a file with:\n"
            "`/addfile Series Name | S01E01 | 720p`\n"
            "`/addfile Series Name | Season 1 | Episode 1 | 1080p`\n"
            "`/addfile Series Name | 480p`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return

    try:
        if len(message.command) < 2:
            await show_addfile_help(message)
            return
            
        command_text = message.text.split(" ", 1)[1]
        parsed = parse_addfile_command(command_text)
        
        if not parsed:
            await show_addfile_help(message)
            return
            
        series_name, season, episode, resolution = parsed
        
        file_info = get_file_info(message.reply_to_message)
        if not file_info:
            await message.reply("Unsupported file type. Please use documents, videos, audio, or animations.")
            return

        # Store file in database channel first
        db_message = await store_file_in_channel(client, message.reply_to_message, series_name, resolution, season, episode)
        if not db_message:
            await message.reply("Failed to store file in database channel.")
            return

        # Store in database with the database message ID
        file_caption = build_file_caption(series_name, season, episode, resolution, file_info)
        
        cursor.execute("""
            INSERT INTO files (series_name, season, episode, resolution, file_id, 
                             message_id, file_type, caption, file_size, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            series_name, season, episode, resolution,
            file_info['id'], db_message.id, file_info['type'],
            file_caption, format_file_size(file_info['size']),
            format_duration(file_info['duration'])
        ))
        conn.commit()

        # Store series mapping
        encoded_name = encode_series_name(series_name)
        store_series_mapping(series_name, encoded_name)

        # Format display for response
        season_episode = f"{season}{episode}" if season and episode else season or episode or "N/A"
        
        await message.reply(
            f"File added successfully!\n\n"
            f"Series: {series_name}\n"
            f"Resolution: {resolution}\n"
            f"Type: {file_info['type'].title()}\n"
            f"Episode: {season_episode}\n"
            f"Size: {format_file_size(file_info['size'])}",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        logger.info(f"Admin {user_id} added file to '{series_name}'")

    except Exception as e:
        logger.error(f"Error in add_file: {e}")
        await message.reply(f"Error: {str(e)}")

async def store_file_in_channel(client, replied_message, series_name, resolution, season, episode):
    """Store file in database channel by forwarding the original message"""
    try:
        # Build caption for the database channel
        caption_parts = [f"{series_name}", f"{resolution}"]
        
        if season and episode:
            caption_parts.append(f"{season}{episode}")
        elif season:
            caption_parts.append(season)
        elif episode:
            caption_parts.append(episode)
            
        caption = " | ".join(caption_parts)
        
        # Forward the message to database channel
        forwarded_msg = await replied_message.forward(DATABASE_CHANNEL)
        
        # Edit the forwarded message caption if possible
        try:
            await client.edit_message_caption(
                chat_id=DATABASE_CHANNEL,
                message_id=forwarded_msg.id,
                caption=caption
            )
        except Exception as e:
            logger.warning(f"Could not edit caption: {e}")
        
        return forwarded_msg
        
    except Exception as e:
        logger.error(f"Error storing file: {e}")
        return None

def build_file_caption(series_name, season, episode, resolution, file_info):
    """Build caption for the file"""
    parts = []
    if season and episode:
        parts.append(f"{season}{episode}")
    elif season:
        parts.append(season)
    elif episode:
        parts.append(episode)
    
    if file_info['duration']:
        parts.append(f"Duration: {format_duration(file_info['duration'])}")
    if file_info['size']:
        parts.append(f"Size: {format_file_size(file_info['size'])}")
    
    return " • ".join(parts) if parts else f"{series_name} - {resolution}"

async def show_addfile_help(message):
    """Show help for /addfile command"""
    help_text = """How to Add Files

Format 1 (Recommended):
`/addfile Series Name | S01E01 | 720p`

Format 2:
`/addfile Series Name | Season 1 | Episode 1 | 1080p`

Format 3 (Simple):
`/addfile Series Name | 480p`

Examples:
• `/addfile Breaking Bad | S01E01 | 1080p`
• `/addfile Game of Thrones | Season 1 | Episode 1 | 720p`
• `/addfile Stranger Things | 480p`

Reply to a file when using this command"""
    
    await message.reply(help_text, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_message(filters.command("files") & filters.private)
async def list_files_handler(client, message):
    """List all files in database (Admin only)"""
    if message.from_user.id not in ADMINS:
        return

    try:
        cursor.execute("""
            SELECT series_name, resolution, COUNT(*) as file_count
            FROM files 
            GROUP BY series_name, resolution
            ORDER BY series_name, resolution
        """)
        results = cursor.fetchall()
        
        if not results:
            await message.reply("No files in database yet")
            return
            
        response = "Files in Database:\n\n"
        current_series = ""
        
        for series, resolution, count in results:
            if series != current_series:
                response += f"**{series}**\n"
                current_series = series
            response += f"  └ {resolution}: {count} files\n"
            
        await message.reply(response, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        await message.reply("Error retrieving files list.")

@app.on_message(filters.command("delete_series") & filters.private)
async def delete_series_handler(client, message):
    """Delete all files of a series (Admin only)"""
    if message.from_user.id not in ADMINS:
        return

    try:
        if len(message.command) < 2:
            await message.reply('Usage: `/delete_series "Series Name"`', parse_mode=enums.ParseMode.MARKDOWN)
            return
            
        series_name = message.text.split(" ", 1)[1].strip().strip('"')
        
        cursor.execute("DELETE FROM files WHERE series_name = ?", (series_name,))
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            await message.reply(f"Deleted {deleted_count} files from '{series_name}'")
        else:
            await message.reply(f"No files found for series '{series_name}'")
        
    except Exception as e:
        logger.error(f"Error deleting series: {e}")
        await message.reply(f"Error: {str(e)}")