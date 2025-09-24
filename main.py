from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
import logging
from utils import encode_series_name, decode_series_name
from shared import app, SPONSOR_CHANNEL, DATABASE_CHANNEL, MAIN_CHANNEL, ADMINS
from database import get_database_stats

# Enhanced logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import database connection and register handlers
from database import conn, cursor
import files
import episodes

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Enhanced start command with menu"""
    welcome_text = """
🎬 **Welcome to TV Series Bot!**

I help you download your favorite TV series episodes easily.

**Features:**
• 📺 Browse available series
• 🎯 Multiple resolutions (480p, 720p, 1080p)
• ⚡ Fast direct downloads
• 📱 Mobile optimized

Use the buttons below to get started!"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Browse Series", callback_data="series_list")],
        [InlineKeyboardButton("🔍 Search Series", callback_data="search_series")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help_menu"),
         InlineKeyboardButton("📊 Stats", callback_data="stats_menu")]
    ])
    
    if message.from_user.id in ADMINS:
        welcome_text += "\n\n👑 **Admin Mode Activated**"
        keyboard.row(InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel"))
    
    await message.reply(welcome_text, reply_markup=keyboard, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = """
📖 **TV Series Bot Help**

**For Users:**
• Browse series using the menu
• Join required channels when prompted
• Select resolution and episode
• Files are sent to your DM

**For Admins:**
`/addfile Series Name | S01E01 | 720p` (reply to file)
`/sendseries Series Name` (optionally reply to image)
`/viewfiles` - View all files in database
`/stats` - Bot statistics

**Need Help?**
If you encounter issues:
1. Make sure you've started a chat with the bot
2. Check if you've joined required channels
3. Try again after a few minutes

**Supported File Types:**
📄 Documents, 🎬 Videos, 🎵 Audio, 🎞️ Animations
    """
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Start Browsing", callback_data="series_list")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])
    
    await message.reply(help_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)

@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client, message):
    """Show bot statistics"""
    if message.from_user.id not in ADMINS:
        await message.reply("❌ Admin only command.")
        return
    
    try:
        stats = get_database_stats()
        stats_text = f"""
📊 **Bot Statistics**

**Database:**
• Total Series: `{stats.get('total_series', 0)}`
• Total Files: `{stats.get('total_files', 0)}`
• Total Downloads: `{stats.get('total_downloads', 0)}`

**Channels:**
• Main Channel: `{MAIN_CHANNEL or 'Not set'}`
• Database Channel: `{DATABASE_CHANNEL or 'Not set'}`
• Sponsor Channel: `{SPONSOR_CHANNEL or 'Not set'}`

**Admins:** `{len(ADMINS)}` users
        """
        await message.reply(stats_text, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await message.reply("❌ Error generating statistics.")

# Enhanced series posting with error handling
@app.on_message(filters.command("sendseries") & filters.private)
async def send_series(client, message):
    if message.from_user.id not in ADMINS:
        logger.warning(f"Unauthorized sendseries attempt by user {message.from_user.id}")
        await message.reply("❌ You are not authorized.")
        return

    try:
        if len(message.command) < 2:
            await message.reply("⚠️ Usage: `/sendseries Series Name`")
            return
            
        series_name = message.text.split(" ", 1)[1].strip()
        
        if not series_name:
            await message.reply("❌ Series name cannot be empty.")
            return
            
        encoded_name = encode_series_name(series_name)
        
        # Check if series has files in database
        cursor.execute("SELECT COUNT(*) FROM files WHERE series_name=?", (series_name,))
        file_count = cursor.fetchone()[0]
        
        if file_count == 0:
            await message.reply(f"❌ No files found for series '{series_name}'. Add files first using /addfile.")
            return
        
        # Create the inline keyboard
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Series", callback_data=f"series_{encoded_name}")],
            [InlineKeyboardButton("📊 View Episodes", callback_data=f"preview_{encoded_name}")]
        ])
        
        # Enhanced caption with file count
        caption = f"""**{series_name}**

🎬 Complete Series Available
📺 {file_count} Episodes • Multiple Qualities
⭐ Organized and Easy to Download

Tap **Download** below to get started 👇"""
        
        # Check if the message is a reply to an image
        if message.reply_to_message and message.reply_to_message.photo:
            await app.send_photo(
                chat_id=MAIN_CHANNEL,
                photo=message.reply_to_message.photo.file_id,
                caption=caption,
                reply_markup=keyboard
            )
            await message.reply(f"✅ Series post with image sent to channel! ({file_count} files)")
        else:
            # Enhanced text message with formatting
            text_message = f"""**{series_name}** - Complete Series

📁 {file_count} Episodes Available
🎯 Multiple Resolutions: 480p, 720p, 1080p
⚡ Fast Direct Download

Click **Download** to browse episodes 👇"""
            
            await app.send_message(
                chat_id=MAIN_CHANNEL,
                text=text_message,
                reply_markup=keyboard
            )
            await message.reply(f"✅ Series post sent to channel! ({file_count} files)")
            
        logger.info(f"Series '{series_name}' posted by admin {message.from_user.id}")

    except Exception as e:
        logger.error(f"Error in sendseries: {e}")
        await message.reply(f"⚠️ Error: {str(e)}")

# Enhanced series selection with better error handling
@app.on_callback_query(filters.regex(r"^series_(.+)$"))
async def series_selected(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_", 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id

        logger.info(f"User {user_id} selected series: {series_name}")

        # Check if SPONSOR_CHANNEL is configured and required
        if SPONSOR_CHANNEL:
            # Check if user is already a member
            try:
                member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
                if member.status not in ["left", "kicked"]:
                    # User is already a member, show resolutions directly
                    await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
                    return
            except Exception as e:
                logger.warning(f"Could not check membership for {user_id}: {e}")
                # Continue to show join button if check fails

            # Send join requirement message
            try:
                chat = await client.get_chat(SPONSOR_CHANNEL)
                invite_link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else SPONSOR_CHANNEL
                
                join_message = await client.send_message(
                    chat_id=user_id,
                    text=f"**{series_name}**\n\n📢 Please join our channel to access the episodes:\n\n@{chat.username or SPONSOR_CHANNEL}",
                    parse_mode=enums.ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=invite_link)],
                        [InlineKeyboardButton("✅ I've Joined", callback_data=f"check_{encoded_name}")]
                    ])
                )
                await callback_query.answer("📨 Check your DM for further instructions!")
            except (UserIsBlocked, PeerIdInvalid):
                # If bot can't message user, send in current chat
                chat = await client.get_chat(SPONSOR_CHANNEL)
                invite_link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else SPONSOR_CHANNEL
                
                await callback_query.message.reply(
                    f"**{series_name}**\n\n📢 Please join our channel first:\n\n@{chat.username or SPONSOR_CHANNEL}",
                    parse_mode=enums.ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=invite_link)],
                        [InlineKeyboardButton("✅ I've Joined", callback_data=f"check_{encoded_name}")]
                    ])
                )
                await callback_query.answer()
        else:
            # No sponsor channel required, show resolutions directly
            await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            
    except Exception as e:
        logger.error(f"Error in series_selected: {e}")
        await callback_query.answer("❌ Error processing your request.", show_alert=True)

# Enhanced subscription check
@app.on_callback_query(filters.regex(r"^check_(.+)$"))
async def check_subscription(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_", 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id

        if not SPONSOR_CHANNEL:
            await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            return

        try:
            # Check if user is member of sponsor channel
            member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
            if member.status not in ["left", "kicked"]:
                await callback_query.answer("✅ Access granted!", show_alert=False)
                await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            else:
                await callback_query.answer("❌ You haven't joined the channel yet!", show_alert=True)
        except Exception as e:
            logger.error(f"Unable to verify channel membership for {user_id}: {e}")
            await callback_query.answer("❌ Please make sure you've joined and try again.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in check_subscription: {e}")
        await callback_query.answer("❌ Error processing your request.", show_alert=True)

# Enhanced resolution selection
@app.on_callback_query(filters.regex(r"^res_(.+)_(.+)$"))
async def resolution_selected(client, callback_query):
    try:
        parts = callback_query.data.split("_")
        encoded_name = parts[1]
        resolution = parts[2]
        series_name = decode_series_name(encoded_name)

        # Show episode list for this resolution (page 0)
        await episodes.list_series(client, callback_query, encoded_name, series_name, resolution, 0)
        
    except Exception as e:
        logger.error(f"Error in resolution_selected: {e}")
        await callback_query.answer("❌ Error loading episodes.", show_alert=True)

# Admin panel callback
@app.on_callback_query(filters.regex(r"^admin_panel$"))
async def admin_panel(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        await callback_query.answer("❌ Admin access required.", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 View Stats", callback_data="view_stats"),
         InlineKeyboardButton("📁 View Files", callback_data="view_files_db")],
        [InlineKeyboardButton("🔄 Cleanup DB", callback_data="cleanup_db")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])
    
    await callback_query.message.edit(
        "🛠️ **Admin Panel**\n\nSelect an action:",
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

if __name__ == "__main__":
    print("🎬 TV Series Bot is starting...")
    logger.info("Bot started successfully")
    app.run()