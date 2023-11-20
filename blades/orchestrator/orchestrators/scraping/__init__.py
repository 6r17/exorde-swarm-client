"""

Orchestrate scraping wich is the result of

    scraper configuration & Version + keyword

    - scraper_configuration = which modules are used
    - keywords = which keyword are used

    Which should result in

        [ Module , ModuleVersion, KeyWord ]

"""

import time
import logging
from dataclasses import dataclass

from .scraper_configuration import get_scrapers_configuration
from .keywords import choose_keyword
from .weighted_choice import weighted_choice

from ...intent import Intent

import random
from typing import Union

blade_logger = logging.getLogger('blade')

"""
Choosing which domain is scrapped is done using a weighted_choice algorithm
(see weighted_choice.py for more on this subject)
"""

async def choose_domain(weights: dict[str, float], *layers 
) -> str:  # this will return "twitter" "weibo" etc...
    matrix: list[dict[str, float]] = [weights, *layers]
    return weighted_choice(matrix)


"""
    We can configure different features using vectors.


                             quota
                               │   ┌─ focus
                         .1  x 1 x 1 = .1,
                         .2  x 1 x 0 =  0,
                         .3  x 0 x 1 =  0
    scraper configuration ┘             │
                                        │
                        weighted_choice(r) => domain to scrap


    scraper configuration => scraper ponderation
    quotas                => 1 | 0 depending on qt of items retrieved
    focus                 => 1 | 0 depending on the user preferences

    quotas are used to limit the amount of items collected from a scraper per
    24 hours

    focus allow the user to restrict which modules are used.

    weighted_choice uses dict (indexed by id) instead of lists, which allows us
    to provide incomplete weights and those are managed correctly

"""
async def generate_focus_layer(blade, weights: dict[str, float]) -> dict[str, float]:
    """ returning an empty dict makes no change """
    onlies: list[str] = blade['static_cluster_parameters']['focus']
    return {k: 1.0 if k in onlies else 0.0 for k, __v__ in weights.items()}

"""

"""


def get_blades_location(topology, blade_type: str) -> list[str]:
    """return a list hosts that match blade_type"""
    result = []
    for blade in topology['blades']:
        if blade['blade'] == blade_type:
            result.append('{}:{}'.format(blade['host'], blade['port']))
    return result


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


async def scraping_orchestration(
    blade, capabilities: dict[str, str], topology: dict
) -> Union[None, Intent]:
    try:
        scrapers_configuration = get_scrapers_configuration()
    except:
        blade_logger.exception("Error retriving scrapers configuration")
        return # having no scrapers_configuration available is a critical error
               # do nothing for now but it does not resolve the situation

    # quota_layer: dict[str, float] = await generate_quota_layer(
    #     blade, counter
    # ) # todo
    # todo : user module overwrite
    # todo_next : try_except + loggings

    # focus_layer is configured by user and allows him to focus on spsc scrapers
    try:
        focus_layer: dict[str, float] = await generate_focus_layer(
            blade, scrapers_configuration.weights,
        )
    except:
        blade_logger.exception(
            "Error while instanciating focus vector, ignoring feature"
        )
        focus_layer = {}

    try:
        domain = await choose_domain(
            scrapers_configuration.weights, focus_layer
        )
    except:
        blade_logger.exception(
            "Error while choosing_domain, skipping intent"
        )
        return

    # get the appropriate scraping module for `domain`, for now, the first [0] 
    scraper_module:str = scrapers_configuration.enabled_modules[domain][0]

    # todo note : remove scrapers_configuration from choose_keyword
    # it is currently used for keyword_alg which is mistakenly part of
    # scrapers_conf
    [keyword, __keyword_alg__] = await choose_keyword(
        scraper_module.__name__, scrapers_configuration
    )

    module = "exorde-labs/rss007d0675444aa13fc"
    return Intent[ScraperIntentParameters](
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        host='{}:{}'.format(blade['host'], blade['port']),
        blade='scraper',
        version=capabilities['exorde-labs/exorde-swarm-client'],
        params=ScraperIntentParameters(
            module=module,
            version=capabilities[module],
            target='http://{}/push'.format(
                random.choice(get_blades_location(topology, 'spotting'))
            ),
            keyword=keyword,
            parameters={

            }
        )
    )
