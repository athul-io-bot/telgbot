from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
from shared import app, ADMINS, DATABASE_CHANNEL
from utils import decode_series_name
from database import cursor
import logging

logger = logging.getLogger(__name__)

def format_episode_button(episode_data, index):
    """Format episode button with enhanced metadata"""
    file_id, caption, season, episode, resolution, file_type = episode_data
    
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
        parts.append(f"File {index + 1}")
    
    # Add file type icon
    type_icons = {
        'video': '🎬',
        'document': '📄',
        'audio': '🎵',
        'animation': '🎞️'
    }
    icon = type_icons.get(file_type, '📁')
    parts.append(icon)
    
    return " • ".join(parts)

# List episodes with pagination - Enhanced with metadata
async def list_series(client, callback_query, encoded_name, series_name, resolution, page):
    try:
        cursor.execute("""
            SELECT file_id, caption, season, episode, resolution, file_type 
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

        per_page = 6  # Increased for better mobile experience
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
        total_pages = (len(files) + per_page - 1) // per_page
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"list_{encoded_name}_{resolution}_{page-1}"))
        
        # Page indicator with total files info
        nav_buttons.append(InlineKeyboardButton(f"📖 {page+1}/{total_pages}", callback_data="none"))
        
        if end < len(files):
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"list_{encoded_name}_{resolution}_{page+1}"))

        if nav_buttons:
            buttons.append(nav_buttons)
        
        # Back to resolutions button
        buttons.append([InlineKeyboardButton("🔙 Back to Resolutions", callback_data=f"back_{encoded_name}")])

        # Enhanced title with episode count
        episode_count = len(files)
        start_ep = start + 1
        end_ep = min(end, episode_count)
        
        title = f"**{series_name}**\n"
        title += f"🎯 **Resolution:** {resolution}\n"
        title += f"📂 **Episodes:** {start_ep}-{end_ep} of {episode_count}\n\n"
        title += "Select an episode to download:"
        
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
            await callback_query.message.edit("❌ No files available for this series.")
            return
            
        buttons = []
        for res, count in resolutions:
            button_text = f"{res} 📁 ({count} files)"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"res_{encoded_name}_{res}")])
        
        # Add series list button
        buttons.append([InlineKeyboardButton("📋 All Series", callback_data="series_list")])
        
        await callback_query.message.edit(
            f"**{series_name}**\n\nAvailable resolutions:\n",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in back_to_resolutions: {e}")
        await callback_query.answer("Error going back.", show_alert=True)

# Send selected episode - FIXED VERSION
@app.on_callback_query(filters.regex(r"^file_(.+)$"))
async def send_episode(client, callback_query):
    """Send an episode to the user by copying from database channel"""
    try:
        file_id = callback_query.data.split("_", 1)[1]
        
        # Get file details from database including message_id
        cursor.execute("""
            SELECT message_id, caption, series_name, season, episode, resolution, file_type 
            FROM files 
            WHERE file_id=?
        """, (file_id,))
        row = cursor.fetchone()
        
        if not row:
            await callback_query.answer("❌ File not found in database.", show_alert=True)
            return
            
        message_id, caption, series_name, season, episode, resolution, file_type = row
        
        # Build enhanced caption
        enhanced_caption = f"**{series_name}**"
        if season and episode:
            enhanced_caption += f"\n🎬 {season} {episode}"
        elif season:
            enhanced_caption += f"\n🎬 {season}"
        elif episode:
            enhanced_caption += f"\n🎬 {episode}"
            
        enhanced_caption += f"\n📺 **Resolution:** {resolution}"
        
        if caption:
            enhanced_caption += f"\n\n📝 {caption}"
        
        enhanced_caption += f"\n\n✅ **Downloaded via @{client.me.username}**"
        
        try:
            # Copy message from database channel to user (MOST RELIABLE METHOD)
            await client.copy_message(
                chat_id=callback_query.from_user.id,
                from_chat_id=DATABASE_CHANNEL,
                message_id=message_id,
                caption=enhanced_caption,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            await callback_query.answer("✅ Episode sent to your DM!")
            
        except UserIsBlocked:
            await callback_query.answer("❌ You blocked the bot. Please unblock and start chat.", show_alert=True)
        except PeerIdInvalid:
            await callback_query.answer("❌ Please start a chat with the bot first!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error sending episode: {e}")
        await callback_query.answer("❌ Failed to send file. Please start the bot first!", show_alert=True)

# Series list handler
@app.on_callback_query(filters.regex(r"^series_list$"))
async def show_series_list(client, callback_query):
    """Show list of all available series"""
    try:
        cursor.execute("""
            SELECT series_name, COUNT(*) as file_count 
            FROM files 
            GROUP BY series_name 
            ORDER BY series_name
        """)
        series_list = cursor.fetchall()
        
        if not series_list:
            await callback_query.answer("❌ No series available yet.", show_alert=True)
            return
        
        from utils import encode_series_name
        
        buttons = []
        for series_name, file_count in series_list:
            encoded_name = encode_series_name(series_name)
            button_text = f"📺 {series_name} ({file_count} files)"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"series_{encoded_name}")])
        
        # Add back button
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await callback_query.message.edit(
            "**📺 Available Series**\n\nSelect a series to browse:",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error showing series list: {e}")
        await callback_query.answer("Error loading series list.", show_alert=True)

# Main menu handler
@app.on_callback_query(filters.regex(r"^main_menu$"))
async def main_menu(client, callback_query):
    """Return to main menu"""
    try:
        await callback_query.message.edit(
            "**🎬 TV Series Bot**\n\nBrowse available series or use commands below:",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📺 Browse Series", callback_data="series_list")],
                [InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")],
                [InlineKeyboardButton("🔍 Search", callback_data="search_series")]
            ])
        )
    except Exception as e:
        await callback_query.answer("Welcome!", show_alert=True)

# Handle none callback (page number button)
@app.on_callback_query(filters.regex(r"^none$"))
async def handle_none(client, callback_query):
    await callback_query.answer()