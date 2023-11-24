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
import asyncio
from aiohttp import web, ClientSession, ClientTimeout
from dataclasses import asdict
from typing import Union
import logging

from .versioning import versioning_on_init, RepositoryVersion
from .orchestrators import ORCHESTRATORS
from .intent import Intent

blade_logger = logging.getLogger('blade')

"""
Resolvers are the interface trough which we can express scrappers behavior
changes.

They are tailored for different types of nodes (scraper, spotting, quality)
and allow us to re-configure the node at runtime.
"""
async def think(app) -> dict[str, Intent]: # itent.id : intent
    """
    Low Level `Brain`:
        Generate an index of intents for every node
    """
    # get the version map (versioning.py)
    capabilities_list: list[RepositoryVersion] = await app['version_manager'].get_latest_valid_tags_for_all_repos()
    capabilities: dict[str, str] = { # path : tag_name
        repository_versioning.repository_path: repository_versioning.tag_name
        for repository_versioning in capabilities_list
    }

    async def resolve(node: dict) -> Union[Intent, None]:
        """
        Intents are results of orchestration rules that we define for each node.
        """
        orchestrator = ORCHESTRATORS.get(node['blade'], None)
        if orchestrator: # skip for undefined orchestration
            return await orchestrator(node, capabilities, app['topology'], app['blade'])

    # generate intent list
    result: dict[str, Intent] = {} # id : intent(id,...)
    for node in app['topology']['blades']:
        new_intent: Union[Intent, None] = None
        try:
            new_intent = await resolve(node)
        except:
            """
            There is no fallback strategy in case we are failing to create 
            Intents ATM.
            """
            blade_logger.exception(
                "An error occured creating an intent for {}".format(node),
                extra={
                    'logtest': { 'capabilities': capabilities }
                }
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
            __feedback_vector__ = await asyncio.gather(
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
    try:
        await versioning_on_init(app)
        app['orchestrate'] = app.loop.create_task(orchestrate(app))
    except Exception as err:
        blade_logger.exception(
            "Critical occured initialing versioning, cannot start the client"
        )
        await asyncio.sleep(200)
        raise(err)

async def orchestrator_on_cleanup(app):
    app['orchestrate'].cancel()
    await app['orchestrate']


app = web.Application()
app.on_startup.append(orchestrator_on_init)
app.on_cleanup.append(orchestrator_on_cleanup)
