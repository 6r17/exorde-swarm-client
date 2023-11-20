# scraper.py
import asyncio
from aiohttp import web, ClientSession
import subprocess
import sys
import os
import logging
from importlib import import_module, metadata
import time

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
        self.task = None
  
    def install_module(self, intent): # cannot fail
        """
        install the correct version specified in the intent,

        this cost a process restart and will render the blade un-operant until
        the next intent round has been processed even tough it is restarted.

        """
        try:
            # repository_path = "owner/path"
            repository_path = intent['params']['module']
            # becomes /path
            module_name = os.path.basename(intent['params']['module'].rstrip("/"))
            # hard-locks us to github
            subprocess.check_call(
                [
                    "pip", 
                    "install", 
                    f"git+https://github.com/{repository_path}.git@{intent['params']['version']}#egg={module_name}"
                ]
            )
        except (subprocess.CalledProcessError):
            """
            The install process is locked
                - the blade cannot install new modules
                - alert the user
                - the blade might be inoperant
                - can we only restart ? -> this did not solve the problem
            """
        except PackageNotFoundError:
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
        # in every case we restart the process with the same arguments
        os.execl(sys.executable, sys.executable, *sys.argv)

    def load_intent(self, intent): # cannot fail
        """
        Load an intent sent by the orchestrator.
            - checks wether specified scraping module has correct version
                - install the module if not
            - loads the module
        """
        """Prepare the intent digestion"""
        blade_logger.info('loading intent')
        try:
            # {owner}/{path} becomes {path} 
            module_name = os.path.basename(intent['params']['module'].rstrip("/"))
            install_required:bool = False
            local_version: Union[None, str] = None
            try:
                local_version = metadata.version(module_name)
                """install if the package is absent"""
            except metadata.PackageNotFoundError:
                install_required = True
            finally:
                """install if the package version differs"""
                if local_version != intent['params']['version']:
                    install_required = True

            """
            Logs the intent digestion
            """
            intent_resolution = {
                'local_version': local_version,
                'intent_version': intent['params']['version'],
                'install_required': install_required,
            }
            if install_required:
                install_id = '{}:{}'.format(time.time(), intent['host']) 
                intent_resolution['install'] = install_id

            blade_logger.info('load_intent', extra={
                'logtest': {
                    'intents': {
                        intent['id']: {
                            'resolution': {
                                intent['host']: intent_resolution
                            }
                        }
                    }
                }
            })

            """
            Depending if the install is required the intent should either
                - install the package
                or
                - load the package
            """

            if install_required:
                self.install_module(intent) # will exit the process
            else:
                if self.task == None:
                    blade_logger.info('Creating scraping task')
                    self.task = asyncio.create_task(self.start_scraping(intent))
                else:
                    pass
                    # stop task & reload
        except Exception as err:
            blade_logger.exception('error in load_intent : {}'.format(err))

    async def start_scraping(self, intent:dict): # cannot fail
        # assume the passed module always contains the github prefix
        scraping_module_name:str = module_name = os.path.basename(intent['params']['module'].rstrip("/"))
        blade_logger.info('start_scraping : {}'.format(scraping_module_name))
        parameters = {}
        try:
            scraper_module = import_module(scraping_module_name)
            scraper_generator = scraper_module.query(intent['params']['parameters'])
        except:
            blade_logger.exception('An error occured while loading {}'.format(scraping_module_name))
        finally:
            async for item in scraper_instance:
                blade_logger.info('found new data', extra={
                    'printonly': {
                        'item': item
                    }
                })
                try:
                    await self.push_data(item)
                except:
                    logging.exception('An error occured pushing data')
   
    async def push_data(self, data): # CANNOT FAIL
        """
        Pushing data should never be blocking

        May propagate unreachable to the orchestrator
            multiple strategies possibles:
                - [CHOOSEN] drop de data
                - [COMPLEX] hold the data until capability 
        """
        blade_logger.info('pushing data')
        target = self.intent['params']['target']
        # Assuming that 'data' is a dictionary that can be turned into JSON
        try:
            async with ClientSession() as session:
                async with session.post(target, json=data) as response:
                    response_data = await response.text() 
                    blade_logger.info(f"Status: {response.status}")
                    blade_logger.info(f"Response: {response_data}")
        except:
            blade_logger.exception('Could not push data')


async def load_intent(request):
    """
    used by blade.py on load_intent (basicly a super)

    this is used to manage the versioning of scraping modules
    """
    intent = await request.json()
    request.app['scraper'].load_intent(intent)
    return web.json_response(request.app['node'])

app = web.Application()
app['scraper'] = Scraper()
app['load_intent'] = load_intent
