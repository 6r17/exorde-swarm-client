from aiohttp import web, ClientSession, UnixConnector
from asyncio import gather, create_task, Lock, CancelledError
import logging
import json
import os

blade_logger = logging.getLogger('blade')

class AsyncAggregator:
    """Log aggregation interface used in every format."""
    def __init__(self):
        self.state = {}
        self._listeners = set()

    async def push(self, data):
        """Asynchronously adds a log line to the state. """
        def deep_merge(a, b):
            """ Merges two dictionaries, 'a' and 'b', recursively. """
            result = dict(a)  # Make a copy of a to avoid modifying it
            for k, v in b.items():
                if k in a and isinstance(a[k], dict) and isinstance(v, dict):
                    result[k] = deep_merge(a[k], v)
                else:
                    result[k] = v
            return result

        d = data['_details']
        await self.broadcast(data['_details'])
        self.state = deep_merge(self.state, json.loads(data['_details']))

    async def broadcast(self, message):
        for ws in self._listeners:
            await ws.send_str(message)

    def add_listener(self, ws):
        self._listeners.add(ws)
        ws.send_str(json.dumps(self.state))

    def remove_listener(self, ws):
        self._listeners.discard(ws)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app['log_aggregator'].add_listener(ws)
    try:
        async for msg in ws:
            pass
    finally:
        request.app['log_aggregator'].remove_listener(ws)
    return ws

async def handle_logs(request):
    """Endpoint to receive logs (used in bare)"""
    data = await request.json()
    await request.app['log_aggregator'].push(data)
    return web.Response(text='Log received')

async def get_containers_ids() -> list[str]:
    """Retrieve container_ids that have label "exorde:monitor"""
    url = "http://localhost/containers/json"
    async with ClientSession(connector=UnixConnector(path='/var/run/docker.sock')) as session:
        async with session.get(url) as response:
            containers = await response.json()
            return [container['Id'] for container in containers if 'exorde' in container['Labels'] and container['Labels']['exorde'] == 'monitor']

async def get_logs(session, container_id, log_aggregator):
    """Processes the log stream from a Docker container."""
    url = f"http://localhost/containers/{container_id}/logs?stdout=1&stderr=1&ansi=false&follow=1"
    async with session.get(url) as response:
        blade_logger.info(f"consuming : {url}")
        try:
            while True:
                header = await response.content.readexactly(8)
                stream_type, length = header[0], int.from_bytes(header[4:], "big")
                message = await response.content.readexactly(length)
                try:
                    data = json.loads(message.decode())
                    if data:
                        await log_aggregator.push(data)
                except json.JSONDecodeError:
                    blade_logger.exception("Error decoding JSON")
        except CancelledError:
            blade_logger.info("Log stream cancelled")
        except Exception as e:
            blade_logger.exception("An error occurred: %s", str(e))

async def start_background_tasks(app):
    blade_logger.info("Starting docker log collection")
    app['log_aggregator'] = AsyncAggregator()
    container_ids = await get_containers_ids()
    blade_logger.info(container_ids)
    session = ClientSession(connector=UnixConnector(path="/var/run/docker.sock"))
    app['session'] = session
    tasks = [create_task(get_logs(session, container_id, app['log_aggregator'])) for container_id in container_ids]
    app['log_tasks'] = tasks

async def cleanup_background_tasks(app):
    for task in app.get('log_tasks', []):
        task.cancel()
    await gather(*app.get('log_tasks', []), return_exceptions=True)
    await app['session'].close()

app = web.Application()
app.router.add_post('/logs', handle_logs)
app.router.add_get('/ws', websocket_handler)
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

