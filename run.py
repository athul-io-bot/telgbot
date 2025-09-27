#!/usr/bin/env python3
"""
TV Series Bot - Startup Script
Handles graceful startup and shutdown
"""

import asyncio
import signal
import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'DATABASE_CHANNEL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Please check your .env file and ensure all required variables are set.")
        return False
    
    return True

def setup_directories():
    """Create necessary directories"""
    directories = ['data', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

async def main():
    """Main startup function"""
    print("🎬 TV Series Bot Starting...")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    try:
        # Import and start the bot
        from main import app, logger
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print(f"\n📴 Received signal {signum}, shutting down...")
            logger.info(f"Received signal {signum}, shutting down gracefully")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("✅ Bot started successfully!")
        print("📡 Press Ctrl+C to stop the bot")
        
        # Run the bot
        await app.start()
        await app.idle()
        
    except KeyboardInterrupt:
        print("\n📴 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)
    finally:
        try:
            await app.stop()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())