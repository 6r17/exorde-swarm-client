# scraper.py
import argparse
import asyncio
from aiohttp import web, ClientSession
import subprocess
import pkg_resources
import sys
import os
import logging
from importlib import import_module, metadata


blade_logger = logging.getLogger('blade')

class Scraper:
    """
    Scraper.py uses a scraping modules and pushes it's results to a spotting
    blade

    The scraper is configured using the load_intent endpoint and method.

    note: some methods are marked as 'cannot fail' and should be read as 
        "this function should NEVER fail"
        as such they should have their own error management.
    """
    def __init__(self):
        self.is_active = False  # Controls whether the scraper is active or not
  
    def install_module(self, intent): # cannot fail
        """
        install the correct version specified in the intent,

        this cost a process restart and will render the blade un-operant until
        the next intent round has been processed even tough it is restarted.

        """
        try:
            # repository_path = "owner/path"
            repository_path = intent['params']['module']
            # this hard-locks us to github
            subprocess.check_call(
                [
                    "pip", 
                    "install", 
                    f"git+https://github.com/{repository_path}.git"
                ]
            )
        except (subprocess.CalledProcessError) as e:
            """
            The install process is locked
                - the blade cannot install new modules
                - alert the user
                - the blade might be inoperant
                - can we only restart ? -> this did not solve the problem
            """
            os._exit(1)
        except PackageNotFoundError as e:
            # the package tag should be marked as faulty
            """
            2 strategies:
                - wait (the package is unaccessible)
                - after N sec/min raise that package is unaccessible
                    -> orch should mark package as such
                        -> try again later
                        -> raise err to protocol ?
                            -> network orchestrate (% who has the problem ?)
                                -> alert
                                -> fallback
            """
        os._exit(0) 

    def load_intent(self, intent): # cannot fail
        """
        Load an intent sent by the orchestrator.
            - checks wether specified scraping module has correct version
                - install the module if not
            - loads the module
        """
        # {owner}/{path} becomes {path} 
        module = os.path.basename(intent['params']['module'].rstrip("/"))
        blade_logger.info('loading intent')
        try:
            local_version = metadata.version(module_name)
        except metadata.PackageNotFoundError:
            self.install_module(intent)
        except Exception as e:
            # unhandled error should:
                # (IF they are not metadata's fault)
                #   mark package's version as faulty
                # (IF they are metadata's fault)
                #   mark the client's version as faulty
            pass
        finally:
            if local_version != intent['params']['version']:
                self.install_module(intent)
            else:
                self.module = import_module(module_name)

    async def start_scraping(self): # cannot fail
        bade_logger.info('Start scraping')
        self.is_active = True
        async for data in self.data_generator():
            if not self.is_active: 
                break
            await self.push_data(data)
    
    def stop_scraping(self):
        self.is_active = False

    async def data_generator(self):
        while self.is_active:
            data = "some scraped data"
            yield data
            await asyncio.sleep(1)
    
    async def push_data(self, data): # CANNOT FAIL
        """
        Pushing data should never be blocking

        May propagate unreachable to the orchestrator
            multiple strategies possibles:
                - [CHOOSEN] drop de data
                - [COMPLEX] hold the data until capability 
        """
        blade_logger.info('pushing data')
        async with ClientSession() as session:
            # Assuming that 'data' is a dictionary that can be turned into JSON
            try:
                async with session.post(
                    'http://127.0.0.1:8081/add', json=data
                ) as response:
                    response_data = await response.text() 
                    blade_logger.info(f"Status: {response.status}")
                    blade_logger.info(f"Response: {response_data}")
            except:
                blade_logger.error('Could not push data')


def stop_scraping(request):
    """Cancel the scraper task"""
    blader_logger.info('stop scraping')
    scraper_task = request.app.get('scraper_task')
    if scraper_task:
        scraper_task.cancel()
        request.app['scraper'].stop_scraping()


async def start_scraping(request):
    """Create a task for the scraper to run in the background"""
    request.app['scraper_task'] = asyncio.create_task(
        request.app['scraper'].start_scraping()
    )

async def load_intent(request):
    """
    used by blade.py on load_intent (basicly a super)

    this is used to manage the versioning of scraping modules
    """
    intent = await request.json()
    blade_logger.info('scraper load_intent : {}, {}'.format(intent, request.app['scraper']))
    request.app['scraper'].load_intent(intent)
    return web.json_response(request.app['node'])

app = web.Application()
app['scraper'] = Scraper()
app['load_intent'] = load_intent
