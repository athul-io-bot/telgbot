from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, MessageNotModified
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from database import cursor, conn
from utils import encode_series_name, decode_series_name, store_series_mapping
from shared import app, SPONSOR_CHANNEL, DATABASE_CHANNEL, MAIN_CHANNEL, ADMINS


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Rotating file handler (keeps logs manageable)
log_file = Path(__file__).parent.joinpath('logs', 'bot.log')
log_file.parent.mkdir(parents=True, exist_ok=True)
rot_handler = RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=3)
rot_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
rot_handler.setFormatter(formatter)
logging.getLogger().addHandler(rot_handler)

logger = logging.getLogger(__name__)
# Import handlers after logging setup
import files
import episodes

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    """Welcome message for users with parameter handling"""
    user = message.from_user
    is_admin = user.id in ADMINS
    
    # Check if start parameter contains series info
    start_param = message.command[1] if len(message.command) > 1 else None
    
    if start_param:
        logger.info(f"Start parameter received: {start_param}")
        if start_param.startswith("series_"):
            encoded_name = start_param.replace("series_", "")
            logger.info(f"Extracted encoded name: {encoded_name}")
            await handle_series_start(client, message, encoded_name)
            return
    
    welcome_text = f"""Welcome to @Request_rawbot, {user.first_name}❗

This bot help you download TV series episodes easily and quickly.

• Browse available series
• Multiple resolutions (480p, 720p, 1080p)

{"**Admin Mode Activated**" if is_admin else ""}

Use the buttons below to get started!"""

    keyboard = [
        [InlineKeyboardButton("🔎Browse Series", callback_data="browse_series")],
        [InlineKeyboardButton("⭕Help", callback_data="show_help")]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("Admin Panel", callback_data="admin_panel")])
    
    await message.reply(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=enums.ParseMode.MARKDOWN
    )

async def handle_series_start(client, message, encoded_name):
    """Handle series start from main channel link"""
    try:
        user_id = message.from_user.id
        logger.info(f"User {user_id} started with encoded name: {encoded_name}")
        
        series_name = decode_series_name(encoded_name)
        logger.info(f"Decoded series name: {series_name}")
        
        if series_name == "Unknown Series":
            await message.reply("Invalid series link or series not found. Please try again from the main channel.")
            return
        
        logger.info(f"User {user_id} started with series: {series_name}")
        
        # Check sponsor channel requirement
        if SPONSOR_CHANNEL:
            try:
                member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
                if member.status not in ["left", "kicked"]:
                    # User is member, show resolutions directly
                    await send_resolutions_message(client, message, encoded_name, series_name)
                    return
            except Exception as e:
                logger.warning(f"Could not check membership for {user_id}: {e}")
                # If sponsor channel is invalid/inaccessible, skip the requirement
                logger.info(f"Skipping sponsor channel requirement due to channel access issue")
                await send_resolutions_message(client, message, encoded_name, series_name)
                return

            # Ask user to join channel
            await ask_to_join_sponsor(client, message, encoded_name, series_name)
        else:
            # No sponsor channel required
            await send_resolutions_message(client, message, encoded_name, series_name)
            
    except Exception as e:
        logger.error(f"Error in handle_series_start with encoded_name '{encoded_name}': {e}")
        await message.reply("Error processing your request. Please try again or contact admin.")

async def ask_to_join_sponsor(client, message, encoded_name, series_name):
    """Ask user to join sponsor channel"""
    try:
        chat = await client.get_chat(SPONSOR_CHANNEL)
        
        # Try to get invite link, fallback to username
        if hasattr(chat, 'invite_link') and chat.invite_link:
            invite_link = chat.invite_link
        elif hasattr(chat, 'username') and chat.username:
            invite_link = f"https://t.me/{chat.username}"
        else:
            invite_link = f"https://t.me/{SPONSOR_CHANNEL}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel", url=invite_link)],
            [InlineKeyboardButton("I've Joined", callback_data=f"check_{encoded_name}")]
        ])
        
        await message.reply(
            f"**{series_name}**\n\nPlease join our channel to access episodes:",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error asking to join sponsor: {e}")
        # If sponsor channel is inaccessible, skip requirement and show resolutions
        logger.info(f"Sponsor channel inaccessible, skipping requirement for {series_name}")
        await send_resolutions_message(client, message, encoded_name, series_name)

async def send_resolutions_message(client, message, encoded_name, series_name):
    """Send resolutions selection message"""
    try:
        # Create a mock callback query for the episodes function
        class MockCallback:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
                
            async def reply(self, text, **kwargs):
                return await message.reply(text, **kwargs)
                
        mock_callback = MockCallback(message)
        await episodes.show_resolutions(client, mock_callback, encoded_name, series_name)
        
    except Exception as e:
        logger.error(f"Error sending resolutions message: {e}")
        await message.reply("Error loading series. Please try again.")

@app.on_message(filters.command("help"))
async def help_handler(client, message):
    """Help command"""
    help_text = """**TV Series Bot Help**

**For Users:**
• Use /start to see available series
• Browse and select episodes
• Files are sent to your private messages

**For Admins:**
• /addfile - Add new files to series
• /files - View all files in database
• /stats - View bot statistics
• /delete_series - Remove a series

**Supported File Types:**
Documents, Videos, Audio, Animations

**Need Help?**
If you encounter issues:
1. Make sure you've started the bot
2. Check if you've joined required channels
3. Contact admin for support"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Browsing", callback_data="browse_series")],
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ])
    
    await message.reply(help_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)

@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client, message):
    """Bot statistics (Admin only)"""
    if message.from_user.id not in ADMINS:
        await message.reply("Admin access required.")
        return
    
    try:
        # Get statistics
        cursor.execute("SELECT COUNT(DISTINCT series_name) FROM files")
        series_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM files")
        files_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM download_stats")
        result = cursor.fetchone()
        users_count = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) FROM download_stats")
        result = cursor.fetchone()
        downloads_count = result[0] if result else 0
        
        stats_text = f"""**Bot Statistics**

**Database:**
• Series: `{series_count}`
• Files: `{files_count}`
• Users: `{users_count}`
• Downloads: `{downloads_count}`

**Channels:**
• Database: `{DATABASE_CHANNEL}`
• Main: `{MAIN_CHANNEL or 'Not set'}`
• Sponsor: `{SPONSOR_CHANNEL or 'Not set'}`"""
        
        await message.reply(stats_text, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await message.reply("Error generating statistics.")

@app.on_callback_query(filters.regex(r"^browse_series$"))
async def browse_series_handler(client, callback_query):
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
            await callback_query.answer("No series available yet", show_alert=True)
            return
        
        buttons = []
        for series_name, file_count in series_list:
            encoded_name = encode_series_name(series_name)
            button_text = f"{series_name} ({file_count} files)"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"series_{encoded_name}")])
        
        buttons.append([InlineKeyboardButton("Main Menu", callback_data="main_menu")])
        
        try:
            await callback_query.message.edit_text(
                "**Available Series**\n\nSelect a series to browse episodes:",
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except MessageNotModified:
            pass
        
    except Exception as e:
        logger.error(f"Error browsing series: {e}")
        await callback_query.answer("Error loading series", show_alert=True)

@app.on_callback_query(filters.regex(r"^show_help$"))
async def show_help_handler(client, callback_query):
    """Show help via callback"""
    help_text = """**TV Series Bot Help**

**For Users:**
• Use /start to see available series
• Browse and select episodes
• Files are sent to your private messages

**For Admins:**
• /addfile - Add new files to series
• /files - View all files in database
• /stats - View bot statistics
• /delete_series - Remove a series

**Supported File Types:**
Documents, Videos, Audio, Animations

**Need Help?**
If you encounter issues:
1. Make sure you've started the bot
2. Check if you've joined required channels
3. Contact admin for support"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Browsing", callback_data="browse_series")],
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ])
    
    try:
        await callback_query.message.edit_text(
            help_text, 
            parse_mode=enums.ParseMode.MARKDOWN, 
            reply_markup=keyboard
        )
    except MessageNotModified:
        pass

@app.on_callback_query(filters.regex(r"^series_(.+)$"))
async def series_selected_handler(client, callback_query):
    """Handle series selection"""
    try:
        encoded_name = callback_query.data.split('_', 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id
        
        if series_name == "Unknown Series":
            await callback_query.answer("Invalid series selection", show_alert=True)
            return
        
        logger.info(f"User {user_id} selected series: {series_name}")

        # Check sponsor channel requirement
        if SPONSOR_CHANNEL:
            try:
                member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
                if member.status not in ["left", "kicked"]:
                    # User is member, show resolutions directly
                    await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
                    return
            except Exception as e:
                logger.warning(f"Could not check membership: {e}")
                # If sponsor channel is invalid/inaccessible, skip the requirement
                logger.info(f"Skipping sponsor channel requirement for callback due to channel access issue")
                await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
                return

            # Ask user to join channel
            try:
                chat = await client.get_chat(SPONSOR_CHANNEL)
                
                # Try to get invite link
                if hasattr(chat, 'invite_link') and chat.invite_link:
                    invite_link = chat.invite_link
                elif hasattr(chat, 'username') and chat.username:
                    invite_link = f"https://t.me/{chat.username}"
                else:
                    invite_link = f"https://t.me/{SPONSOR_CHANNEL}"
                
                # Try to send DM first
                try:
                    await client.send_message(
                        chat_id=user_id,
                        text=f"**{series_name}**\n\nPlease join our channel to access episodes:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Join Channel", url=invite_link)],
                            [InlineKeyboardButton("I've Joined", callback_data=f"check_{encoded_name}")]
                        ]),
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    await callback_query.answer("Check your DM for instructions!")
                except (UserIsBlocked, PeerIdInvalid):
                    # Can't DM user, send in current chat
                    try:
                        await callback_query.message.edit_text(
                            f"**{series_name}**\n\nPlease join our channel first:",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("Join Channel", url=invite_link)],
                                [InlineKeyboardButton("I've Joined", callback_data=f"check_{encoded_name}")],
                                [InlineKeyboardButton("Back", callback_data="browse_series")]
                            ]),
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    except MessageNotModified:
                        pass
                    await callback_query.answer()
            except Exception as e:
                logger.error(f"Error sending join request: {e}")
                # If sponsor channel is inaccessible, skip requirement and show resolutions
                logger.info(f"Sponsor channel inaccessible, skipping requirement for callback")
                await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
        else:
            # No sponsor channel required
            await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            
    except Exception as e:
        logger.error(f"Error in series selection: {e}")
        await callback_query.answer("Error processing request", show_alert=True)

@app.on_callback_query(filters.regex(r"^check_(.+)$"))
async def check_subscription_handler(client, callback_query):
    """Check if user joined sponsor channel"""
    try:
        encoded_name = callback_query.data.split('_', 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id

        if not SPONSOR_CHANNEL:
            await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            return

        try:
            member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
            if member.status not in ["left", "kicked"]:
                await callback_query.answer("Access granted!", show_alert=True)
                await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            else:
                await callback_query.answer("Please join the channel first!", show_alert=True)
        except Exception as e:
            logger.warning(f"Error verifying subscription: {e}")
            # If sponsor channel is inaccessible, skip requirement and show resolutions
            logger.info(f"Sponsor channel inaccessible, granting access for check handler")
            await callback_query.answer("Access granted!", show_alert=True)
            await episodes.show_resolutions(client, callback_query, encoded_name, series_name)
            
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        await callback_query.answer("Error processing request", show_alert=True)

@app.on_callback_query(filters.regex(r"^admin_panel$"))
async def admin_panel_handler(client, callback_query):
    """Admin panel"""
    if callback_query.from_user.id not in ADMINS:
        await callback_query.answer("Admin access required", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("View Stats", callback_data="view_stats")],
        [InlineKeyboardButton("List Files", callback_data="list_files")],
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ])
    
    try:
        await callback_query.message.edit_text(
            "**Admin Panel**\n\nSelect an action:",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except MessageNotModified:
        pass

@app.on_callback_query(filters.regex(r"^view_stats$"))
async def view_stats_handler(client, callback_query):
    """Show stats via callback"""
    await stats_handler(client, callback_query.message)

@app.on_callback_query(filters.regex(r"^list_files$"))
async def list_files_callback_handler(client, callback_query):
    """Show files list via callback"""
    await files.list_files_handler(client, callback_query.message)

@app.on_callback_query(filters.regex(r"^main_menu$"))
async def main_menu_handler(client, callback_query):
    """Return to main menu"""
    user = callback_query.from_user
    is_admin = user.id in ADMINS
    
    welcome_text = f"""Welcome to @Request_rawbot, {user.first_name}❗

This bot help you download TV series episodes easily and quickly.

• Browse available series
• Multiple resolutions (480p, 720p, 1080p)

{"**Admin Mode Activated**" if is_admin else ""}

Use the buttons below to get started!"""

    keyboard = [
        [InlineKeyboardButton("🔎Browse Series", callback_data="browse_series")],
        [InlineKeyboardButton("⭕Help", callback_data="show_help")]
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("Admin Panel", callback_data="admin_panel")])
    
    try:
        await callback_query.message.edit_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except MessageNotModified:
        pass




@app.on_message(filters.command("sendseries") & filters.private)
async def send_series_handler(client, message):
    """Post series to main channel (Admin only)"""
    if message.from_user.id not in ADMINS:
        await message.reply("Admin access required.")
        return

    if not MAIN_CHANNEL:
        await message.reply("Main channel not configured.")
        return

    try:
        if len(message.command) < 2:
            await message.reply('Usage: `/sendseries "Series Name"`', parse_mode=enums.ParseMode.MARKDOWN)
            return
            
        series_name = message.text.split(" ", 1)[1].strip().strip('"')
        encoded_name = encode_series_name(series_name)
        
        # Check if series exists
        cursor.execute("SELECT COUNT(*) FROM files WHERE series_name = ?", (series_name,))
        file_count = cursor.fetchone()[0]
        
        if file_count == 0:
            await message.reply(f"No files found for '{series_name}'. Add files first.")
            return

        # Get bot username
        bot_me = await client.get_me()
        
        # Create post
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Download Series", url=f"https://t.me/{bot_me.username}?start=series_{encoded_name}")
        ]])
        
        caption = f"""**{series_name}**
🍿Multiple Qualities🍿

Tap **Download** to get started"""

        # Send with image if replied to a photo
        if message.reply_to_message and message.reply_to_message.photo:
            await client.send_photo(
                MAIN_CHANNEL,
                message.reply_to_message.photo.file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await client.send_message(
                MAIN_CHANNEL,
                caption,
                reply_markup=keyboard,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
        await message.reply(f"Series posted to channel! ({file_count} files)")
        
    except Exception as e:
        logger.error(f"Error sending series: {e}")
        await message.reply(f"Error: {str(e)}")

@app.on_message(filters.command("commands") & filters.private)
async def commands_handler(client, message):
    """Show all available bot commands"""
    user = message.from_user
    is_admin = user.id in ADMINS
    
    user_commands = """**📋 Available Commands**

**👤 User Commands:**
• `/start` - Start the bot and browse series
• `/help` - Show help and bot information
• `/commands` - Show this commands list

**📺 How to Use:**
1. Use /start to see all available series
2. Select a series to view available resolutions
3. Choose your preferred quality
4. Episodes will be sent to your DM

**Features:**
• Multiple resolutions (480p, 720p, 1080p)
• Fast downloads
• Mobile optimized"""

    admin_commands = """

**🔧 Admin Commands:**
• `/addfile` - Add new files to series
• `/files` - View all files in database
• `/stats` - View bot statistics
• `/delete_series` - Remove a series and all its files
• `/sendseries` - Post series to main channel

**Admin Usage:**
• Reply to a file with `/addfile Series Name | S01E01 | 720p`
• Use `/delete_series "Series Name"` to remove series
• Use `/sendseries "Series Name"` to post to channel"""

    commands_text = user_commands
    if is_admin:
        commands_text += admin_commands

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton("📺 Browse Series", callback_data="browse_series")]
    ])

    await message.reply(commands_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)

if __name__ == "__main__":
    logger.info("TV Series Bot starting...")
    app.run()