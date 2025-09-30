from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, FloodWait, MessageNotModified
from shared import app, ADMINS, DATABASE_CHANNEL, SPONSOR_CHANNEL
from utils import decode_series_name, log_download
from database import cursor
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

async def show_resolutions(client, callback_query, encoded_name, series_name):
    """Show available resolutions for a series"""
    try:
        cursor.execute("""
            SELECT DISTINCT resolution
            FROM files 
            WHERE series_name = ? 
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
            if hasattr(callback_query, 'answer'):
                await callback_query.answer("No files available for this series", show_alert=True)
            else:
                await callback_query.reply("No files available for this series")
            return

        buttons = []
        for (resolution,) in resolutions:
            # Get file count for this resolution
            cursor.execute("SELECT COUNT(*) FROM files WHERE series_name = ? AND resolution = ?", 
                         (series_name, resolution))
            file_count = cursor.fetchone()[0]
            
            button_text = f"{resolution} ({file_count} files)"
            buttons.append([
                InlineKeyboardButton(button_text, callback_data=f"res_{encoded_name}_{resolution}")
            ])
        
        # Add back button
        buttons.append([InlineKeyboardButton("Back to Series", callback_data="browse_series")])
        
        message_text = (
            f"**{series_name}**\n\n"
            f"Select Resolution:\n\n"
            f"All episodes of the selected resolution will be sent to your DM automatically."
        )
        
        # Check if this is a callback query or regular message
        if hasattr(callback_query, 'message') and hasattr(callback_query, 'answer'):
            try:
                await callback_query.message.edit_text(
                    message_text,
                    parse_mode=enums.ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except MessageNotModified:
                pass
        else:
            # It's a regular message (from start parameter)
            await callback_query.reply(
                message_text,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
    except Exception as e:
        logger.error(f"Error showing resolutions: {e}")
        if hasattr(callback_query, 'answer'):
            await callback_query.answer("Error loading resolutions", show_alert=True)
        else:
            await callback_query.reply("Error loading resolutions. Please try again.")

async def send_all_episodes(client, user_id, series_name, resolution):
    """Send all episodes of a resolution to user"""
    try:
        # Get episodes data
        cursor.execute("""
            SELECT message_id, file_id, caption, season, episode, file_type, file_size, duration
            FROM files 
            WHERE series_name = ? AND resolution = ?
            ORDER BY 
                CASE WHEN season = '' THEN 1 ELSE 0 END,
                CAST(SUBSTR(season, 2) AS INTEGER),
                CASE WHEN episode = '' THEN 1 ELSE 0 END,
                CAST(SUBSTR(episode, 2) AS INTEGER)
        """, (series_name, resolution))
        
        episodes = cursor.fetchall()
        
        if not episodes:
            return False, "No episodes found for this resolution."

        total_episodes = len(episodes)
        sent_count = 0
        errors = 0
        
        # Send initial message
        try:
            progress_msg = await client.send_message(
                user_id,
                f"**Preparing {total_episodes} episodes of {series_name} ({resolution})...**\n\n"
                f"Initializing... (0/{total_episodes})"
            )
        except (UserIsBlocked, PeerIdInvalid):
            return False, "Please start a chat with the bot first."

        for index, episode_data in enumerate(episodes, 1):
            message_id, file_id, caption, season, episode, file_type, file_size, duration = episode_data
            
            # Build caption for user
            file_caption = f"**{series_name}** "
            if season and episode:
                file_caption += f"{season}{episode} "
            elif season:
                file_caption += f"{season} "
            elif episode:
                file_caption += f"{episode} "
            
            file_caption += f"{resolution}\n"      
            file_caption += f"via @{client.me.username}"
            
            try:
                # Copy message from database channel to remove "Forwarded from" badge
                max_retries = 3
                sent_message = None
                
                # Retry only the copying operation
                for retry in range(max_retries):
                    try:
                        # Copy the message from database channel without forwarding badge
                        sent_message = await client.copy_message(
                            chat_id=user_id,
                            from_chat_id=DATABASE_CHANNEL,
                            message_id=message_id,
                            caption=file_caption,
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                        
                        # If copying succeeded, break out of retry loop
                        if sent_message:
                            break
                            
                    except FloodWait as e:
                        if retry == max_retries - 1:
                            raise e
                        wait_time = int(e.value) if hasattr(e, 'value') else 60
                        logger.info(f"Flood wait for {wait_time} seconds, retrying...")
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        if retry == max_retries - 1:
                            raise e
                        await asyncio.sleep(2)
                
                # Log download
                log_download(user_id, series_name, file_id)
                sent_count += 1
                
                # Update progress every 5 episodes or for the last one
                if sent_count % 5 == 0 or sent_count == total_episodes:
                    try:
                        remaining_time = (total_episodes - sent_count) * 2
                        await progress_msg.edit_text(
                            f"**Sending {total_episodes} episodes of {series_name} ({resolution})...**\n\n"
                            f"Progress: {sent_count}/{total_episodes} episodes sent\n"
                            f"Errors: {errors}\n"
                            f"Remaining: ~{remaining_time} seconds"
                        )
                    except Exception as e:
                        logger.warning(f"Could not update progress message: {e}")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error sending episode {index}: {e}")
                errors += 1
                # Continue with next episode even if one fails
        
        # Send completion message
        if sent_count > 0:
            success_message = (
                f"**Forwarded!**\n"
            )
            
            if errors > 0:
                success_message += "Some episodes failed to send. You can try selecting the resolution again to get the missing episodes.\n\n"
            
            success_message += "Enjoy your episodes!"
            
            try:
                await progress_msg.edit_text(success_message)
            except Exception as e:
                await client.send_message(user_id, success_message)
            
            return True, f"Sent {sent_count}/{total_episodes} episodes"
        else:
            await progress_msg.edit_text("Failed to send any episodes. Please try again.")
            return False, "All episodes failed to send"
            
    except Exception as e:
        logger.error(f"Error in send_all_episodes: {e}")
        return False, f"Error: {str(e)}"

@app.on_callback_query(filters.regex(r"^res_(.+)_(.+)$"))
async def resolution_handler(client, callback_query):
    """Handle resolution selection - send all episodes at once"""
    try:
        data_parts = callback_query.data.split('_')
        if len(data_parts) < 3:
            await callback_query.answer("Invalid selection", show_alert=True)
            return
            
        encoded_name = data_parts[1]
        resolution = data_parts[2]
        series_name = decode_series_name(encoded_name)
        user_id = callback_query.from_user.id
        
        await callback_query.answer(f"Preparing {series_name} ({resolution})...")
        
        # Edit message to show processing
        try:
            await callback_query.message.edit_text(
                f"**{series_name}**\nResolution: {resolution}",
           
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except MessageNotModified:
            pass
        except Exception as e:
            logger.warning(f"Could not edit message: {e}")
        
        # Send all episodes
        success, message = await send_all_episodes(client, user_id, series_name, resolution)
        
        if not success:
            try:
                await callback_query.message.edit_text(
                    f"**{series_name}**\nResolution: {resolution}\n\n"
                    f"Download Failed\n\n{message}",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            except Exception as e:
                await client.send_message(
                    user_id,
                    f"**{series_name}**\nResolution: {resolution}\n\n"
                    f"Download Failed\n\n{message}"
                )
            
    except (UserIsBlocked, PeerIdInvalid):
        await callback_query.answer("Please unblock the bot and start chat", show_alert=True)
    except Exception as e:
        logger.error(f"Error in resolution handler: {e}")
        await callback_query.answer("Error sending episodes", show_alert=True)