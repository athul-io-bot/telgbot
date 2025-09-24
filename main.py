from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from utils import encode_series_name, decode_series_name
from shared import app, SPONSOR_CHANNEL, DATABASE_CHANNEL, MAIN_CHANNEL, ADMINS

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Import database connection and register handlers
from database import conn, cursor
import files
import episodes

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Start command handler"""
    if message.from_user.id in ADMINS:
        await message.reply("👋 Welcome Admin! Use /help to see available commands.")
    else:
        await message.reply("👋 Welcome! Browse series in our channel and tap Download to get episodes.")

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = """
📖 **Series Request Bot Help**

**For Admins:**
`/addfile <Series Name>|<Resolution>` (reply to a file)
`/sendseries <Series Name>` (optionally reply to an image)

**Enhanced /addfile Formats:**
• `/addfile Series Name | S01E01 | 720p`
• `/addfile Series Name | Season 1 | Episode 1 | 1080p`
• `/addfile Series Name | 480p` (simple)

**For Users:**
Tap 'Download' on a series post in the channel, join the sponsor channel, choose resolution, and select episodes.

Supported file types: document, video, audio, animation.
💡 *Tip: Reply to an image when using `/sendseries` to attach a poster!*
    """
    await message.reply(help_text, parse_mode=enums.ParseMode.MARKDOWN)

# Handler to send a series message in main channel (admin use only)
@app.on_message(filters.command("sendseries") & filters.private)
async def send_series(client, message):
    if message.from_user.id not in ADMINS:
        logging.warning(f"Unauthorized sendseries attempt by user {message.from_user.id}")
        await message.reply("❌ You are not authorized.")
        return

    try:
        text = message.text.split(" ", 1)[1]
        series_name = text.strip()
        encoded_name = encode_series_name(series_name)
        
        # Create the inline keyboard
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Series", callback_data=f"series_{encoded_name}")]
        ])
        
        # Check if the message is a reply to an image
        if message.reply_to_message and message.reply_to_message.photo:
            # Enhanced caption with formatting
            caption = f"""**{series_name}**

🎬 Complete Series Available
📺 All Episodes • Multiple Qualities
⭐ Organized and Easy to Download

Tap **Download** below to get started 👇"""
            
            await app.send_photo(
                chat_id=MAIN_CHANNEL,
                photo=message.reply_to_message.photo.file_id,
                caption=caption,
                reply_markup=keyboard
            )
            await message.reply("✅ Series post with image sent successfully!")
        else:
            # Enhanced text message with formatting
            text_message = f"""**{series_name}** - Complete Series

📁 All Episodes Available
🎯 Multiple Resolutions: 480p, 720p, 1080p
⚡ Fast Direct Download

Click **Download** to browse episodes 👇"""
            
            await app.send_message(
                chat_id=MAIN_CHANNEL,
                text=text_message,
                reply_markup=keyboard
            )
            await message.reply("✅ Series post sent successfully!")
            
        logging.info(f"Series '{series_name}' posted by admin {message.from_user.id}")

    except Exception as e:
        logging.error(f"Error in sendseries: {e}")
        await message.reply("⚠ Error: Please use format: `/sendseries Series Name`")

# Series selected by user - FIXED callback parsing
@app.on_callback_query(filters.regex(r"^series_(.+)$"))
async def series_selected(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_", 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id

        # Check if SPONSOR_CHANNEL is configured
        if not SPONSOR_CHANNEL:
            # If no sponsor channel, directly show resolutions
            await show_resolutions(client, callback_query, encoded_name, series_name)
            return

        # Send message to user's DM first
        try:
            # Get sponsor channel username without @
            sponsor_username = SPONSOR_CHANNEL.replace('@', '') if SPONSOR_CHANNEL.startswith('@') else SPONSOR_CHANNEL
            
            await client.send_message(
                chat_id=user_id,
                text=f"You selected *{series_name}*. Please join our channel first to access the episodes.",
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Join Channel 🔊", url=f"https://t.me/{sponsor_username}")],
                    [InlineKeyboardButton("✅ I've Joined", callback_data=f"check_{encoded_name}")]
                ])
            )
            await callback_query.answer("Check your DM for further steps!")
        except Exception as e:
            # If bot can't message user, send in current chat
            logging.error(f"Can't DM user: {e}")
            await callback_query.message.reply(
                "Please start a conversation with me first, then try again.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Start Bot", url=f"https://t.me/{app.me.username}")]
                ])
            )
            await callback_query.answer()
            
    except Exception as e:
        logging.error(f"Error in series_selected: {e}")
        await callback_query.answer("Error processing your request.", show_alert=True)

async def show_resolutions(client, callback_query, encoded_name, series_name):
    """Show available resolutions for a series"""
    try:
        # Get available resolutions for this series
        cursor.execute("SELECT DISTINCT resolution FROM files WHERE series_name=?", (series_name,))
        resolutions = cursor.fetchall()
        
        if not resolutions:
            await callback_query.message.edit("❌ No files found for this series.")
            return
            
        # Create resolution buttons
        buttons = []
        for res in resolutions:
            resolution = res[0]
            buttons.append([InlineKeyboardButton(f"{resolution}", callback_data=f"res_{encoded_name}_{resolution}")])
        
        # Edit the original message to show resolutions
        await callback_query.message.edit(
            f"**{series_name}**\nChoose a resolution:",
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logging.error(f"Error showing resolutions: {e}")
        await callback_query.answer("Error loading resolutions.", show_alert=True)

# Subscription check handler - FIXED callback parsing
@app.on_callback_query(filters.regex(r"^check_(.+)$"))
async def check_subscription(client, callback_query):
    try:
        encoded_name = callback_query.data.split("_", 1)[1]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id

        if not SPONSOR_CHANNEL:
            await show_resolutions(client, callback_query, encoded_name, series_name)
            return

        try:
            # Check if user is member of sponsor channel
            member = await client.get_chat_member(SPONSOR_CHANNEL, user_id)
            if member.status not in ["left", "kicked"]:
                await show_resolutions(client, callback_query, encoded_name, series_name)
            else:
                await callback_query.answer("❌ You must join the channel first!", show_alert=True)
        except Exception as e:
            logging.error(f"Unable to verify channel membership: {e}")
            await callback_query.answer("❌ Error verifying channel membership. Please try again.", show_alert=True)
            
    except Exception as e:
        logging.error(f"Error in check_subscription: {e}")
        await callback_query.answer("Error processing your request.", show_alert=True)

# Resolution selected handler - Now show episode list
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
        logging.error(f"Error in resolution_selected: {e}")
        await callback_query.answer("Error loading episodes.", show_alert=True)

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
