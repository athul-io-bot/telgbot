from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shared import app, ADMINS, DATABASE_CHANNEL
from utils import decode_series_name
from database import cursor
import logging

# Add logging
logger = logging.getLogger(__name__)

def format_episode_button(episode_data, index):
    """Format episode button with enhanced metadata"""
    file_id, caption, season, episode, resolution = episode_data
    
    # Create a clean button label
    parts = []
    if season and episode:
        parts.append(f"{season} {episode}")
    elif season:
        parts.append(season)
    elif episode:
        ep_num = episode.replace('Episode', '').strip()
        parts.append(f"Ep {ep_num}")
    else:
        parts.append(f"Episode {index + 1}")
    
    return " • ".join(parts)

# List episodes with pagination - Enhanced with metadata
async def list_series(client, callback_query, encoded_name, series_name, resolution, page):
    try:
        cursor.execute("""
            SELECT file_id, caption, season, episode, resolution 
            FROM files 
            WHERE series_name=? AND resolution=?
            ORDER BY 
                CASE WHEN season = '' THEN 1 ELSE 0 END,
                season,
                CASE WHEN episode = '' THEN 1 ELSE 0 END,
                episode
        """, (series_name, resolution))
        files = cursor.fetchall()

        if not files:
            await callback_query.answer("No episodes available for this resolution.", show_alert=True)
            return

        per_page = 5
        start = page * per_page
        end = start + per_page
        page_files = files[start:end]

        # Create episode buttons with enhanced labels
        buttons = []
        for i, episode_data in enumerate(page_files):
            button_text = format_episode_button(episode_data, start + i)
            file_id = episode_data[0]
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"file_{file_id}")])

        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"list_{encoded_name}_{resolution}_{page-1}"))
        
        # Show total pages info
        total_pages = (len(files) + per_page - 1) // per_page
        nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="none"))
        
        if end < len(files):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"list_{encoded_name}_{resolution}_{page+1}"))

        if nav_buttons:
            buttons.append(nav_buttons)
        
        # Back to resolutions button
        buttons.append([InlineKeyboardButton("↩️ Back to Resolutions", callback_data=f"back_{encoded_name}")])

        # Enhanced title with episode count
        cursor.execute("SELECT COUNT(*) FROM files WHERE series_name=? AND resolution=?", (series_name, resolution))
        episode_count = cursor.fetchone()[0]
        
        title = f"**{series_name}** - {resolution}\n"
        title += f"📁 {episode_count} episode(s) available\n"
        title += "Select an episode:"
        
        await callback_query.message.edit(
            title,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in list_series: {e}")
        await callback_query.answer("Error loading episodes.", show_alert=True)

# Handle pagination callbacks
@app.on_callback_query(filters.regex(r"^list_(.+)_(.+)_(\d+)$"))
async def handle_list_callback(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_")[1]
        resolution = callback_query.data.split("_")[2]
        page = int(callback_query.data.split("_")[3])
        series_name = decode_series_name(encoded_name)
        
        await list_series(client, callback_query, encoded_name, series_name, resolution, page)
        
    except Exception as e:
        logger.error(f"Error in handle_list_callback: {e}")
        await callback_query.answer("Error loading page.", show_alert=True)

# Handle back to resolutions
@app.on_callback_query(filters.regex(r"^back_(.+)$"))
async def back_to_resolutions(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_")[1]
        series_name = decode_series_name(encoded_name)
        
        # Get available resolutions with episode counts
        cursor.execute("""
            SELECT resolution, COUNT(*) as episode_count 
            FROM files 
            WHERE series_name=? 
            GROUP BY resolution
            ORDER BY 
                CASE 
                    WHEN resolution = '1080p' THEN 1
                    WHEN resolution = '720p' THEN 2
                    WHEN resolution = '480p' THEN 3
                    ELSE 4
                END
        """, (series_name,))
        resolutions = cursor.fetchall()
        
        if not resolutions:
            await callback_query.message.edit("❌ No resolutions available.")
            return
            
        buttons = []
        for res, count in resolutions:
            button_text = f"{res} ({count} episodes)"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"res_{encoded_name}_{res}")])
        
        await callback_query.message.edit(
            f"**{series_name}**\nChoose a resolution:",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in back_to_resolutions: {e}")
        await callback_query.answer("Error going back.", show_alert=True)

# Send selected episode with enhanced info - SIMPLIFIED VERSION
@app.on_callback_query(filters.regex(r"^file_(.+)$"))
async def send_episode(client, callback_query):
    try:
        file_id = callback_query.data.split("_", 1)[1]

        cursor.execute("SELECT caption, series_name, season, episode, resolution FROM files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()

        if not row:
            await callback_query.answer("❌ File not found in database.", show_alert=True)
            return

        caption, series_name, season, episode, resolution = row
        
        # Build enhanced caption
        enhanced_caption = f"**{series_name}**"
        if season and episode:
            enhanced_caption += f"\n{season} {episode}"
        elif season:
            enhanced_caption += f"\n{season}"
        elif episode:
            enhanced_caption += f"\n{episode}"
            
        enhanced_caption += f"\n📺 {resolution}"
        
        if caption:
            enhanced_caption += f"\n\n{caption}"

        # SIMPLIFIED FILE SENDING - Just forward the file directly
        try:
            # Forward the file from database channel to user
            await client.forward_messages(
                chat_id=callback_query.from_user.id,
                from_chat_id=DATABASE_CHANNEL,
                message_ids=[await get_message_id(client, file_id)],  # We need to get the message ID
                disable_notification=True
            )
            await callback_query.answer("✅ Episode sent to your DM!")
            
        except Exception as send_error:
            logger.error(f"Failed to forward file: {send_error}")
            # Alternative: try copying the file
            try:
                await client.copy_message(
                    chat_id=callback_query.from_user.id,
                    from_chat_id=DATABASE_CHANNEL,
                    message_id=await get_message_id(client, file_id),
                    caption=enhanced_caption,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                await callback_query.answer("✅ Episode sent to your DM!")
            except Exception as copy_error:
                logger.error(f"Failed to copy file: {copy_error}")
                await callback_query.answer("❌ Failed to send file. Please start the bot first!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        await callback_query.answer("❌ Failed to send file. Please start a conversation with the bot first!", show_alert=True)

async def get_message_id(client, file_id):
    """Get message ID from file_id by searching in database channel"""
    try:
        # This is a simplified version - you might need to store message IDs in database
        # For now, we'll use a workaround by trying to send the file directly
        return None  # We'll handle this differently
    except Exception as e:
        logger.error(f"Error getting message ID: {e}")
        return None

# NEW: Simple file sending using direct file_id
@app.on_callback_query(filters.regex(r"^simplefile_(.+)$"))
async def send_episode_simple(client, callback_query):
    """Simplified file sending using direct file_id"""
    try:
        file_id = callback_query.data.split("_", 1)[1]

        cursor.execute("SELECT caption, series_name, season, episode, resolution FROM files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()

        if not row:
            await callback_query.answer("❌ File not found in database.", show_alert=True)
            return

        caption, series_name, season, episode, resolution = row
        
        # Build enhanced caption
        enhanced_caption = f"**{series_name}**"
        if season and episode:
            enhanced_caption += f"\n{season} {episode}"
        elif season:
            enhanced_caption += f"\n{season}"
        elif episode:
            enhanced_caption += f"\n{episode}"
            
        enhanced_caption += f"\n📺 {resolution}"
        
        if caption:
            enhanced_caption += f"\n\n{caption}"

        # DIRECT FILE SENDING using file_id
        await client.send_document(
            chat_id=callback_query.from_user.id,
            document=file_id,
            caption=enhanced_caption,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        await callback_query.answer("✅ Episode sent to your DM!")
        
    except Exception as e:
        logger.error(f"Error in simple file sending: {e}")
        await callback_query.answer("❌ Failed to send file. Please start the bot first!", show_alert=True)

# Handle none callback (page number button)
@app.on_callback_query(filters.regex(r"^none$"))
async def handle_none(client, callback_query):
    await callback_query.answer()
