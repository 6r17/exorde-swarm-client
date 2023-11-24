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
from typing import Union, Callable

from urllib.parse import urlparse

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
async def generate_focus_layer(
    blade, weights: dict[str, float]
) -> dict[str, float]:
    """ returning an empty dict makes no change """
    try:
        onlies: list[str] = blade['static_cluster_parameters']['focus']
        return {
            k: 1.0 if k in onlies else 0.0 for k, __v__ in weights.items()
        }
    except KeyError as error:
        blade_logger.exception(
            "An error occured while generating focus layer",
            extra={

            }
        )
        raise(error)
   

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
    parameters: dict # regular buisness related parameters
    target: str # spotting host to send data to
    module: str # the scraping module to use
    version: str # the version of scraping module to use

def get_owner_repo_from_github_url(url):
    parsed_url = urlparse(url)
    path = parsed_url.path.strip('/')
    owner_repo = '/'.join(path.split('/')[:2])
    return owner_repo


async def create_intent(
    blade, capabilities: dict[str, str], topology: dict, self_blade
) -> Intent:
    try:
        scrapers_configuration = await get_scrapers_configuration()
    except Exception as err:
        blade_logger.exception("Error retriving scrapers configuration")
        raise(err) # having no scrapers_configuration available is a critical error
                   # do nothing for now but it does not resolve the situation

    # quota_layer: dict[str, float] = await generate_quota_layer(
    #     blade, counter
    # ) # todo
    # todo : user module overwrite
    # todo_next : try_except + loggings

    # focus_layer is configured by user and allows him to focus on spsc scrapers
    try:
        focus_layer: dict[str, float] = await generate_focus_layer(
            self_blade, scrapers_configuration.weights,
        )
    except:
        blade_logger.exception(
            "Error while instanciating focus vector, ignoring feature",
            extra={
                'logtest': blade
            }
        )
        focus_layer = {}

    try:
        domain = await choose_domain(
            scrapers_configuration.weights, focus_layer
        )
    except Exception as err:
        blade_logger.exception(
            "Error while choosing_domain, skipping intent"
        )
        raise(err)

    """get the appropriate scraping module for `domain`, for now, the first [0]"""
    # in url format (eg: "https://github.com/owner/repo")
    scraper_module: str = scrapers_configuration.enabled_modules[domain][0]

    # todo note : remove scrapers_configuration from choose_keyword
    # it is currently used for keyword_alg which is mistakenly part of
    # scrapers_conf
    [keyword, __keyword_alg__] = await choose_keyword(
        scraper_module, scrapers_configuration
    )

    """Scraping parameters"""

    generic_modules_parameters: dict[
        str, Union[int, str, bool, dict]
    ] = scrapers_configuration.generic_modules_parameters

    specific_parameters: dict[
        str, Union[int, str, bool, dict]
    ] = scrapers_configuration.specific_modules_parameters.get(
        scraper_module, {}
    )
    parameters: dict[str, Union[int, str, bool, dict]] = {
        "url_parameters": {"keyword": keyword},
        "keyword": keyword,
    }
    parameters.update(generic_modules_parameters)
    parameters.update(specific_parameters)


    # in `owner/repo` format
    module = get_owner_repo_from_github_url(scraper_module) 
    # hardlocked to exorde-labs
    return Intent[ScraperIntentParameters](
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        host='{}:{}'.format(blade['host'], blade['port']),
        blade='scraper',
        version=capabilities['exorde-labs/exorde-swarm-client'],
        params=ScraperIntentParameters(
            module=module,
            version=capabilities[module],
            target='http://{}/push'.format(
                random.choice(
                    get_blades_location(topology, 'spotting')
                )
            ),
            parameters=parameters
        )
    )

@dataclass
class CurrentIntent:
    intent: Intent
    at: float 


def should_create_new_intent(
    current_intent: Union[CurrentIntent, None]
) -> bool:
    if not current_intent:
        return True
    current_time:float = time.time()
    if current_time - current_intent.at >= 10.0:
        return True
    return False

class ShouldCreateNewIntentError(Exception):
    """
    SHOULD NOT HAPPEN : CHECK FOR NONE
    `should_create_new_intent` did not trigger a intent creation and no intent
    has been retrieved. This error should never happen. It means that both
    `scraping_orchestration` and `should_create_new_intent` have forgot checking 
    `None`.
    """

def create_scraping_orchestration() -> Callable:
    """
    Intents timing control, the orchestrator push intents every seconds, this
    function allows us to use previous intents instead of creating new ones in
    order to control at which rate the different scrapers should change their
    configuration.
    """
    memory = {} # use balde['host'] to differenciate managed hosts
    async def orchestrate(
        blade, capabilities: dict[str, str], topology: dict, self_blade
    ) -> Intent:
        nonlocal memory

        maybe_current_intent: Union[CurrentIntent, None] = memory.get(
            blade['host'], None
        )
        intent: Intent
        if not maybe_current_intent or should_create_new_intent(
            maybe_current_intent
        ):
            """error is managed above and there is no fallback strategy ATM"""
            intent = await create_intent(
                blade, capabilities, topology, self_blade
            )
            return intent
        else:
            if maybe_current_intent:
                current_intent: CurrentIntent = maybe_current_intent
                intent = current_intent.intent
                return intent
        raise ShouldCreateNewIntentError

    return orchestrate

scraping_orchestration = create_scraping_orchestration()
