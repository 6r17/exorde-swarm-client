"""

Orchestrate scraping wich is the result of

    scraper configuration & Version + keyword

    - scraper_configuration = which modules are used
    - keywords = which keyword are used

    Which should result in

        [ Module , ModuleVersion, KeyWord ]

"""


from .scraper_configuration import get_scrapers_configuration
from .keywords import choose_keyword


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
async def generate_quota_layer(
    command_line_arguments: argparse.Namespace, counter: AsyncItemCounter
) -> dict[str, float]:
    """TODO: unmanaged atm"""
    quotas = {k: v for d in command_line_arguments.quota for k, v in d.items()}
    counts = {
        k: await counter.count_occurrences(k) for k, __v__ in quotas.items()
    }
    layer = {
        k: 1.0 if counts[k] < quotas[k] else 0.0 for k, __v__ in quotas.items()
    }
    return layer

async def generate_focus_layer(blade, weights: dict[str, float]) -> dict[str, float]:
    """ returning an empty dict makes no change """
    onlies: list[str] = blade['static_cluster_parameters']['focus']
    return {k: 1.0 if k in onlies else 0.0 for k, __v__ in weights.items()}

"""

"""

def scraping_orchestration(
    blade, capabilities: dict[str, str], topology: dict
) -> Intent:
    try:
        scrapers_configuration = get_scrapers_configuration()
    except:
        blade_logger.exception("Error retriving scrapers configuration")
        return # having no scrapers_configuration available is a critical error
               # to nothing for now but it does not resolve the situation

    # quota_layer: dict[str, float] = await generate_quota_layer(
    #     blade, counter
    # ) # todo
    # todo : user module overwrite
    # todo_next : try_except + loggings

    # focus_layer is configured by user and allows him to focus on spsc scrapers
    try:
        focus_layer: dict[str, float] = await generate_focus_layer(
            blade, ponderation.weights,
        )
    except:
        logging.exception(
            "Error while instanciating focus vector, ignoring feature"
        )
        focus_layer = {}

    try:
        domain = await choose_domain(scrapers_configuration.weights, focus_layer)
    except:
        logging.exception(
            "Error while choosing_domain, skipping intent")
        )
        return

    # get the appropriate scraping module for `domain` 
    scraper_module:str = ponderation.enabled_modules[domain][0]

    # todo note : remove scrapers_configuration from choose_keyword
    keyword = await choose_keyword(module.__name__. scrapers_configuration)

    module = "exorde-labs/rss007d0675444aa13fc"
    return Intent(
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
            keyword="BITCOIN",
            parameters={

            }
        )
    )
