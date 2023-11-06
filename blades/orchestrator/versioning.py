"""
Orchestrator's versioning interface

It it used to retrieve repositorie's tags and versions

The goal is to monitor the version of every module the system is using.
    - client
    - scraping modules

note: exorde_data is not part of this as this dependency is expressed by either
the scraping_modules or the client.

## Breaking change in the schema
This creates a situation where the scraping modules can output data that is
not valid for either the ipfs gateway or even the spotting modules.

Since exorde-data defines the structure of the scraped data, a breaking change
in this schema provokes an automatic peremption of every scraping module.

(Note that this is differented from the Analyzed schema which is a different
pipe but has the same problem)

None-the less ; to properly rollout an update we should primarly update the
orchetrator's version which is going to roll an update on every blade. 

This process would generate errors on the scraping modules and we should
specificly diffrenciate those in order to react accordingly.

There are different scenarios :
    - scraping modules do not have an up to date version for the schema
        -> the scraping module is disabled and the domain is not scrappable
    - scraping module has a new version but does not work
        -> the scraping module is disabled and the domain is not scrappable
    - scraping module is unable to update for misc reason
        -> the scraping module is disabled and the domain is not scrappable
    - scraping module has updated and is working
        -> domain is scrappable

exorde_data is exorde's main control system and is designed as primary source
of truth therfor report and locking out non-working scraping modules should be 
the appropriate behavior of the system in case of such situation.

"""
from packaging import version
import aiohttp

def build_repository_list(orchestrator_configuration):
    pass

from dataclasses import dataclass
from datetime import datetime

@dataclass
class Commit:
    sha: str
    url: str

@dataclass
class GithubTagDetail:
    name: str
    zipball_url: str
    tarball_url: str
    commit: Commit
    node_id: str

@dataclass
class repositoryVersioning:
    repository: str # owner/repository_name
    tags_report: list[GithubTagDetail]
    last_tag_update: datetime

@dataclass
class versionMap:
    repositories: list[repositoryVersioning]


from .async_cache import async_cache

async def get_repository_versioning(repo: str) -> repositoryVersioning:
    async def fetch_json(url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

    tags_url = f"https://api.github.com/repos/{repo}/tags"
    tags = await fetch_json(tags_url)

    # Filter out pre-releases and assume the tags are provided from latest to oldtest
    valid_tags = [tag for tag in tags if not version.parse(tag["name"]).is_prerelease]

    # Create GithubTagDetail objects for each tag in sorted order
    tags_report = [
        GithubTagDetail(
            name=tag["name"],
            zipball_url=tag["zipball_url"],
            tarball_url=tag["tarball_url"],
            commit=Commit(sha=tag["commit"]["sha"], url=tag["commit"]["url"]),
            node_id=tag["node_id"]
        ) for tag in valid_tags 
    ]

    # The last_tag_update is the current time when this function is called
    last_tag_update = datetime.now()

    return repositoryVersioning(
        repository=repo,
        tags_report=tags_report,
        last_tag_update=last_tag_update
    )

async def get_version_map(app) -> versionMap:
    repositories: list[str] = [
        "exorde-labs/exorde-swarm-client",
    ] # include swarm-client by default

    # add every repository listed by the user's configuration
    repositories.extend(app['blade']['static_cluster_paramters']['scrapers'])

    # retrieve thei repository versioning
    repositories_versioning: list[repositoryVersioning] = await asyncio.gather(
        *[get_repository_versioning(repository) for respotiroy in repositories]
    )

    version_map: versionMap = versionMap(
        repositories=repositories_versioning
    )


async def version_on_init(app):
    app['get_repository_versioning' = async_cache(
        max_age=app['blade'].get(
            'static_cluster_parameters', {}).get(
            'github_tags_cache_max_age_in_seconds', 60
        )
    )(get_repository_versioning)
