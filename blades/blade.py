"""
A blade is a generic aiohttp server wrapper that insure different endpoints on 
each blades.

Think of this as a class which blades inherit from (spotting or scrapper)
"""

import os
import argparse
import asyncio
from aiohttp import web
import json
import logging

async def hello(request):
    return web.Response(text="Hello, World!")

async def kill(request):
    os._exit(-1)


"""
here blade is 1 blade configuration eg

  - name: scraper_one
    blade: scraper
    managed: true
    host: 127.0.0.1
    port: 8002
    venv: "./venvs/scraper_one"

weheras topology is the complete configuration file

"""

async def start_blade(blade, topology):
    # If params are provided, set them in the app's shared state
    app['topology'] = topology
    app['blade'] = blade
    await web._run_app(app, host=blade['host'], port=blade['port'])

def app_serializer(obj):
    # Converts any non-serializable object to its string representation
    if isinstance(obj, web.Application):
        # Perform specific serialization for aiohttp web.Application, if needed
        # For example, return a dict of routes. This is just a placeholder.
        return {"routes": list(obj.router.routes())}
    elif callable(obj):
        # Convert callables to their string representation
        return f"Callable: {obj.__name__}" if hasattr(obj, '__name__') else "Unnamed callable"
    else:
        # Default: convert to string
        return str(obj)

async def status(request):
    """get only of below function"""
    app_json = json.dumps(dict(request.app), default=app_serializer)
    print(dict(request.app))
    return web.Response(text=app_json, content_type='application/json')

async def status_set(request):
    """
    The status endpoint is used by the orchestrator to inform intent and retrieve
    status of blade's
        - type
        - configuration
        - status
    """
    intent = await request.json()
    if request.app.get('status_set', None):
        try:
            # we define the interface using request.app internal dict 
            return await request.app['status_set'](request)
        except:
            pass
    # if there is no overwrite we simply return the blade's status
    return web.json_response(request.app['blade'])

"""
Overclassing the blades is done by importing their app definition and overwriting
it here.

Each blade should be launched using this script.
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generic aiohttp server manager")
    parser.add_argument("--blade", type=json.loads, default={}, help="JSON string of blade configuration")
    parser.add_argument("--topology", type=json.loads, default={}, help="JSON string of topology")
    args = parser.parse_args()

    # Dynamically load the appropriate aiohttp app from the subblade
    mod = __import__(args.blade['blade'], fromlist=['app'])
    app = getattr(mod, 'app')
    app['blade'] = args.blade
    app['topology'] = args.topology
    app.router.add_get('/kill', kill)
    app.router.add_get('/', status)
    app.router.add_post('/status', status_set)

    asyncio.run(start_blade(args.blade, args.topology))
