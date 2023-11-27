"""
Spotting server waits to receive data, accumulates it and applies batch logic
on it

"""
from aiohttp import web
import asyncio
import logging

from .spotting_process import spotting_process

blade_logger = logging.getLogger('blade')

# Shared state and lock
shared_data = {'items': []}
lock = asyncio.Lock()

# Maximum size of the list before processing
MAX_SIZE = 10
async def add_data(request):
    """Scrapers push items trough this endpoint"""
    data = await request.text()
    blade_logger.info('Received new data')

    async with lock:
        shared_data['items'].append(data)
        data_size = len(shared_data['items'])

        # If the list reaches MAX_SIZE, trigger processing
        if data_size >= MAX_SIZE:
            # Copy the data for processing and clear the shared state
            data_to_process = shared_data['items'].copy()
            shared_data['items'] = []
            # Run the data processing without holding the lock
            asyncio.create_task(spotting_process(data_to_process))
            return web.Response(
                text=f"Data added and processing triggered with {data_size} items."
            )

    return web.Response(text="Data added.")

app = web.Application()

async def spotting_on_init(app):
    blade_logger.info("Hello World !")

app.on_startup.append(spotting_on_init)

app.router.add_post('/push', add_data)
