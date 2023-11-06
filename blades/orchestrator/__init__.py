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
from aiohttp import web, ClientSession
from dataclasses import dataclass, asdict
from typing import Union
import json


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
    extra_parameters: dict # regular buisness related parameters
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

def scraping_resolver(blade) -> Intent:
    """
    Using resolvers we can configure blades parameters such as keywords, timeout
    etc... but most importantly the version of modules. The blade will be able
    to re-install a new version in it's venv and restart*.

    *not a container-stop but a process-stop 
    """
    return Intent(
        host='{}:{}'.format(blade['host'], blade['port']),
        blade='scraper',
        version='0.1',
        params=ScraperIntentParameters(
            module="exorde-labs/rss007d0675444aa13fc",
            version="0.0.3",
            target="resolve_to_a_spotting_host",
            keyword="BITCOIN",
            extra_parameters={

            }
        )
    )

def spotting_resolver(blade) -> Intent:
    """The spotting resolver has no special implementation on static top"""
    return Intent(
        blade='spotting', # we never change a blade's behavior in static top
        version='0.1',
        host='{}:{}'.format(blade['host'], blade['port']),
        params=SpottingIntentParameters() # does nothing for spotting, maybe pass worker addr
    )

def orchestrator_resolver(blade) -> Intent:
    """The orchestrator resolver has no special implementation on static top"""
    return Intent(
        blade='orchestrator',
        version='0.1',
        host='{}:{}'.format(blade['host'], blade['port']),
        params=OrchestratorIntentParameters() # does nothing for orch,  NOTE : both need to control
                                                                              # version
    )

RESOLVERS = {
    'scraper': scraping_resolver,
    'spotting': spotting_resolver,
    'orchestrator': orchestrator_resolver
}

def think(app) -> list[Intent]:
    """
    Low Level Note:

    Analog to the brain but instead of generating keywords in generate a list
    of nodes that should be at a specific state, difference here is that:

        - The result now includes the spotting module as the orchestrator should
        theoreticly specify the behavior of every node
        (this would allow us to change the behavior of a node if we are balancing)
    
        - The keyword configuration now also includes the version of the scraping
        module to use.

    note: 

        - The overall idea behind this architecture is to assume an instable
        software which may interup at anytime (due to pip installs & exit) ; 

        - it also provides us a way to assume the status of the system and have
        enough data available in order to change the behavior or even topology
        of the system.

        (eg data / failure rate of module/version for behavior)
        (   and capacity evaluation based on spotting threshold )
        (   so for this we would need a way to evaluate nodes capacity )

    For example we will be able in the future to switch from a 4-scrappers 1 
    spotter to 3 scrapper 2 spotters if the spotter is getting overwhelmed.

    ===========================================================================


    Buisness Related Goals:
        - each module should know:
            - what module with which version it sould use
            - what keyword it should scrap with
            - and have it's specific parameters

    """
    
    # get the version map (versioning.py)

    # generate intent list
    result: list[Intent] = []
    def resolve(node: dict) -> Intent:
        return RESOLVERS[node['blade']](node)

    for node in app['topology']['blades']:
        result.append(resolve(node))
    return result
"""
# Orchestrator algorithm in pseudo-code:

    - think
        - what should be correct configuration ?
            - what are the modules to use ?
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
async def orchestrate(app):
    """
    goal:
        - make sure that scrapers run correct parameters
            - keyword
            - domain_parameters
    """

    while True:
        await asyncio.sleep(1) # to let the servers set up
        brain_map = think(app)

        await asyncio.sleep(app['check_interval'] - 1)

async def orchestrator_on_init(app):
    # start_background_tasks
    app['orchestrate'] = app.loop.create_task(orchestrate(app))

async def orchestrator_on_cleanup(app):
    app['orchestrate'].cancel()
    await app['orchestrate']

app = web.Application()
app.on_startup.append(orchestrator_on_init)
app.on_startup.append(version_on_init)
app.on_cleanup.append(orchestrator_on_cleanup)

app['check_interval'] = 10  # check every 10 seconds
