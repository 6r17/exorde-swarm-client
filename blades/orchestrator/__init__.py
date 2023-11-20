"""
The orchestrator is a python process which controls a cluster of exorde blades.

It interface with blade.py which is a exorde-cluster-client module. 

It's goal is to keep the cluster properly configured under exorde's and user's 
parameters.

1. Version control
    the orchestrator should be able to make a report on the version being used
    by the blade and what best version should be used. 

    In order to do that we need to:
        - update the scraping module if there is a new version
        - mark a version as deffective and prevent scraping-blades from
            using it. Effectively rolling back by skipping this version.
        - Report on versions being used by modules
        - Report on versions available

2. Perf control 
    the orchestrator should be able to measure the performance of different
    modules and provide a report on it. (not for this PR)

"""
import time
import asyncio
from aiohttp import web, ClientSession, ClientTimeout
from dataclasses import dataclass, asdict
from typing import Union
import json
import random
import logging

from .versioning import versioning_on_init, RepositoryVersion
from .orchestrators import ORCHESTRATORS

"""
# Intents.

Intents are designed as a configuration rather than instructions. The goal is
therefor to start, stop, re-configure different modules rather than specificly
follow each instruction and centralize them.

For example for scrapping the interface design is the following :
"""
@dataclass
class ScraperIntentParameters:
    """
    note that both scraping modules and blades are versioned and that is because
    they are different entities. Scraping modules have their own version and
    repositories.

    Both are differenciated and handled in the orchestrator differently.

    The scraper.py blade therfor contains two versioning systems :

        - blade versioning (blade.py) which controls the blade's code
        - scraping versioning (scraper.py) which controls the scraper's code
    """
    keyword: str # the keyword to scrap
    parameters: dict # regular buisness related parameters
    target: str # spotting host to send data to
    module: str # the scraping module to use
    version: str # the version of scraping module to use

@dataclass
class SpottingIntentParameters:
    """
    For now there is no specific configuration around the Spotting module
    because it's main_address is configured trough config which is sufficient 
    for static topology.
    """
    pass

@dataclass
class OrchestratorIntentParameters:
    """Does-Nothing"""
    pass


@dataclass
class Intent:
    """
    Intents are wrapped to contain a host (they always are meant to an entity)
    """
    id: str # time:host
    host: str # including port
    blade: str # blade to use
    version: str # blade's version
    params: Union[
        SpottingIntentParameters, 
        ScraperIntentParameters,
        OrchestratorIntentParameters,
    ]

"""
Resolvers are the interface trough which we can express scrappers behavior
changes.

They are tailored for different types of nodes (scraper, spotting, quality)
and allow us to re-configure the node at runtime.

"""

def get_blades_location(topology, blade_type: str) -> list[str]:
    """return a list hosts that match blade_type"""
    result = []
    for blade in topology['blades']:
        if blade['blade'] == blade_type:
            result.append('{}:{}'.format(blade['host'], blade['port']))
    return result

async def think(app) -> dict[str, Intent]: # itent.id : intent
    """
    Low Level `Brain`:

        Generate an index of intents for every node

    """
    # get the version map (versioning.py)
    capabilities: list[RepositoryVersiong] = await app['version_manager'].get_latest_valid_tags_for_all_repos()
    capabilities: dict[str, str] = { # path : tag_name
        repository_versioning.repository_path: repository_versioning.tag_name
        for repository_versioning in capabilities
    }

    def resolve(node: dict) -> Intent:
        """
        intents are results of orchestration rules that we define for each node.
        """
        orchestrator = ORCHESTRATORS.get(node['blade'], None)
        if orchestrator: # skip for undefined orchestration
            return orchestrator(node, capabilities, app['topology'])

    # generate intent list
    result: dict[str, Intent] = {} # id : intent(id,...)
    for node in app['topology']['blades']:
        try:
            new_intent = resolve(node)
        except:
            blade_logger.exception(
                "An error occured creating an intent for {}".format(node)
            )
        finally:
            if new_intent: # intents can return None to skip silently (bad)
                result[new_intent.id] = new_intent
            else:
                blade_logger.warning(
                    "Orchestration result was empty for {}".format(node)
                )
    return result

"""
# Orchestrator algorithm in pseudo-code:
    - think
        - what should be correct configuration ?
            - what are the modules to use ?
                - [versioning] what are available modules to be used ?
            - what are the parameters to use for those modules ?
    - monitor
        - for each blade
            - is blade on correct configuration ? 
                - NO
                    - stop it
                    - configure the scraper
                    - start it

note : 
    start / stop can have different meanings :
        - process stop (due to update)
        - software stop (implemented in blade/scraper.py) which does not stop
            the process
"""


blade_logger = logging.getLogger('blade')

async def commit_intent(intent: Intent):
    async with ClientSession(timeout=ClientTimeout(1)) as session:
        host = 'http://' + intent.host
        try:
            async with session.post(host, json=asdict(intent)) as response:
                return response
        except:
            # the blade is non responsive which can happen atm when the module pip installs
            blade_logger.warning('Could not reach {}'.format(host))

async def orchestrate(app):
    """
    goal:
        - make sure that scrapers run correct parameters
            - keyword
            - domain_parameters
    """
    while True:
        try:
            await asyncio.sleep(1) # to let the servers set up
            indexed_intents = await think(app)
            blade_logger.info('intent vector initialized', extra={
                'logtest': { 'intents': indexed_intents }
            })
            feedback_vector = await asyncio.gather(
                *[commit_intent(
                    indexed_intents[intent_id]
                ) for intent_id in indexed_intents]
            )
            await asyncio.sleep(
                app['blade']['static_cluster_parameters']['orchestrator_interval_in_seconds'] - 1
            )
        except:
            blade_logger.exception('An error occured in the orchestrator')
            blade_logger.info(app['blade']['static_cluster_parameters'])


async def orchestrator_on_init(app):
    # orchestrate is a background task that runs forever
    app['orchestrate'] = app.loop.create_task(orchestrate(app))

async def orchestrator_on_cleanup(app):
    app['orchestrate'].cancel()
    await app['orchestrate']

app = web.Application()
app.on_startup.append(orchestrator_on_init)
app.on_startup.append(versioning_on_init)
app.on_cleanup.append(orchestrator_on_cleanup)
