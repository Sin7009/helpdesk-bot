#!/usr/bin/env python
"""
Start the Telegram Mini App web server.

Usage:
    python start_webapp.py
"""
import asyncio
import logging
from webapp.server import start_webapp


async def main():
    """Start the web server and run forever."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    runner = await start_webapp()
    
    try:
        # Run forever
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Web server stopped")
