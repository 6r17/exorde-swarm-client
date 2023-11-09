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

None-the less ; to properly rollout an update we should primarily update the
orchetrator's version which is going to roll an update on every blade. 

This process would generate errors on the scraping modules and we should
specificly differentiate those in order to react accordingly.

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

import logging
import asyncio
from packaging import version
import aiohttp
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from asyncdb import AsyncDB, AsyncPool
from typing import Optional

class Mark(Enum):
    """
    `mark` is an internal `label` system differenciated from online labels.
    """
    DEFFECTIVE = 0

@dataclass
class Commit:
    sha: str
    url: str

@dataclass
class Tag:
    name: str
    zipball_url: str
    tarball_url: str
    commit: Commit
    node_id: str
    repository: Optional[str] # not returned by the API, used by sync

@dataclass
class Repository:
    path: str # owner/repository_name
    tags: list[Tag]


async def get_repository_versioning(repo: str) -> Repository:
    """Retrieves a repository available tags ; repo is owner/path"""
    async def fetch_json(url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

    tags_url = f"https://api.github.com/repos/{repo}/tags"
    tags = await fetch_json(tags_url)

    # Filter out pre-releases
    valid_tags = [
        tag for tag in tags if not version.parse(tag["name"]).is_prerelease
    ]

    # Create Tag objects for each tag in sorted order
    tags = [
        Tag(
            name=tag["name"],
            zipball_url=tag["zipball_url"],
            tarball_url=tag["tarball_url"],
            commit=Commit(sha=tag["commit"]["sha"], url=tag["commit"]["url"]),
            node_id=tag["node_id"],
            repository=None
        ) for tag in valid_tags 
    ]


    return Repository(path=repo, tags=tags)


@dataclass
class RepositoryVersion:
    """
        RepositoryVersion is source of truth for version that should be used.
        This is the expected output of get_latest_vald_tags_fo_all_repos()
        which reflects the latest working capabilities for inputed repositories
    """
    repository_path: str
    tag_name: str

class VersionManager:
    """
    The goal of the VersionManager is to propose an interface for version
    tracking.
        - to "mark" a tag as DEFFECTIVE if it doesn't work
        - a method to retrieve the latest working tag repositories
        - a method to sync tags from the repository hub
    """
    def __init__(self, blade):
        database_parameters = blade['static_cluster_parameters']['db']
        self.db = AsyncDB(
            blade['static_cluster_parameters']['database_provider'], 
            params=database_parameters
        )
        self.github_cache_threshold_minutes = blade['static_cluster_parameters'].get(
            'github_cache_threshold_minutes', 10
        )
        repositories: list[str] = [
            "exorde-labs/exorde-swarm-client",
        ] # includes every blade
        # and add every repository listed by the user's configuration
        repositories.extend(blade['static_cluster_parameters']['scrapers'])
        self.repositories = repositories

    async def set_up(self):
        async with await self.db.connection() as conn:
            # todo : checks
            result, error = await conn.execute('''
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    last_online_retrieval DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            logging.info('repositories table creation : {}, {}'.format(result, error))

            result, error = await conn.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repository INTEGER,
                    name TEXT NOT NULL,
                    zipball_url TEXT,
                    tarball_url TEXT,
                    _commit TEXT,
                    FOREIGN KEY (repository) REFERENCES repositories(id)
                    UNIQUE (repository, name)
                );
            ''')

            logging.info('tags table creation -> {}, {}'.format(result, error))

            result, error = await conn.execute('''
                CREATE TABLE IF NOT EXISTS marks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id INTEGER,
                    mark INTEGER NOT NULL,
                    FOREIGN KEY (tag_id) REFERENCES tags (id)
                    UNIQUE (tag_id, mark)
                );
            ''')

            logging.info('marks table creation : {}, {}'.format(result, error))

    async def sync(self, cache=True):
        """Synchronize repository tags with online version."""
        threshold_time = datetime.utcnow() - timedelta(minutes=self.github_cache_threshold_minutes)
        # Convert threshold_time to a format suitable for SQLite comparison
        formatted_threshold_time = threshold_time.strftime('%Y-%m-%d %H:%M:%S')


        async with await self.db.connection() as conn:
            if cache:
                # Get repositories that need updating based on the threshold
                (repos_to_update, error) = await conn.query(
                    'SELECT path FROM repositories WHERE last_online_retrieval < :formated_threshold_time',
                    formated_threshold_time=formatted_threshold_time
                )

                # Create a list of repositories that need to be synced
                repos_to_sync_paths = [row[0] for row in repos_to_update]

                # Filter self.repositories based on repos_to_sync_paths
                repositories_to_sync = [repo for repo in self.repositories if repo in repos_to_sync_paths]

                # Gather repository data asynchronously for repositories that need updating
                repositories = await asyncio.gather(
                    *[get_repository_versioning(repo) for repo in repositories_to_sync]
                )
            else:
                repositories = await asyncio.gather(
                    *[get_repository_versioning(repo) for repo in self.repositories]
                )


            inserted_repositories = [
                (repository.path,) for repository in repositories
            ]
            await conn.executemany(
                '''
                INSERT INTO repositories(path) VALUES (?)
                ON CONFLICT(path) DO UPDATE SET
                    last_online_retrieval = CURRENT_TIMESTAMP;
                ''', 
                inserted_repositories
            )

            (identified_repositories, error) = await conn.query(
                'SELECT * FROM repositories'
            )


            def identify(repository: str, identified_repositories) -> int:
                for identified_repository in identified_repositories:
                    if identified_repository[1] == repository:
                        return identified_repository[0]

            inserted_tags = []
            for repository in repositories:
                for tag in repository.tags:
                    line = [
                        identify(repository.path, identified_repositories),
                        tag.name,
                        tag.zipball_url,
                        tag.tarball_url,
                        tag.commit.url,
                    ]
                    inserted_tags.append(tuple(line))

            logging.info(inserted_tags)
            await conn.executemany(
                'INSERT OR IGNORE INTO tags(repository, name, zipball_url, tarball_url, _commit) VALUES (?, ?, ?, ?, ?)',
                inserted_tags
            )

    async def get_latest_valid_tags_for_all_repos(self):
        """
        Retrieves the latest valid tag for each repository.
        """
        async with await self.db.connection() as conn:
            # Get all tags for all repositories, excluding defective ones
            query = """
                SELECT r.path, t.name
                FROM tags t
                JOIN repositories r ON t.repository = r.id
                LEFT JOIN marks m ON m.tag_id = t.id AND m.mark = :mark_value
                WHERE m.id IS NULL;
            """

            # Execute the query
            (tag_rows, error) = await conn.query(query, mark_value=Mark.DEFFECTIVE.value)
            if error:
                # Handle error here
                logging.info("Error fetching tags:", error)
                return []

            # Create a dictionary to collect tags per repository path
            repositories_with_tags = {}
            for repo_path, tag in tag_rows:
                if repo_path not in repositories_with_tags:
                    repositories_with_tags[repo_path] = []
                repositories_with_tags[repo_path].append(tag)

            # Create a list to collect the latest RepositoryVersion per repository
            repository_versions = []
            
            """
            If a repository has no non-defective tags, its corresponding tags
            list will be empty, and the if condition will fail, preventing the
            addition of a RepositoryVersion for that repository.

            This effectively filters out repositories without valid tags from
            the final results.
            """

            # Sort tags for each repository and create RepositoryVersion for the latest
            for repo_path, tags in repositories_with_tags.items():
                if tags:  # Check if there are any tags to sort
                    latest_tag = max(tags, key=lambda t: version.parse(t))
                    repository_versions.append(
                        RepositoryVersion(
                            repository_path=repo_path, 
                            tag_name=latest_tag
                        )
                    )

            return repository_versions

    async def mark_tag_as(self, tag_name: str, repository_path: str, mark: Mark):
        """Mark a tag with a given status."""
        async with await self.db.connection() as conn:
            # First find the tag id by joining with the repositories table.
            # This requires the repository path and the tag name to identify the right tag.
            tag_query_result, tag_error = await conn.query(
                """
                SELECT t.id FROM tags t
                JOIN repositories r ON t.repository = r.id
                WHERE r.path = :repository_path AND t.name = :tag_name;
                """,
                repository_path=repository_path, tag_name=tag_name
            )

            if tag_error:
                logging.info(f"Error finding tag to mark: {tag_error}")
                return
            
            # Check if tag exists
            if not tag_query_result:
                logging.info(f"No tag found for {repository_path} with name {tag_name}")
                return

            tag_id = tag_query_result[0][0]

            # Insert or update the mark for this tag.
            mark_result, mark_error = await conn.execute(
                """
                INSERT INTO marks (tag_id, mark)
                VALUES (:tag_id, :mark_value)
                """,
                tag_id=tag_id, mark_value=mark.value
            )

            if mark_error:
                logging.info(f"Error marking tag: {mark_error}")
            else:
                logging.info(f"Tag {tag_name} marked as {mark} for {repository_path}")

    async def delete_mark_from_tag(self, tag_name: str, repository_path: str, mark: Mark):
        """Delete a mark from a tag."""
        async with await self.db.connection() as conn:
            # First find the tag id by joining with the repositories table.
            tag_query_result, tag_error = await conn.query(
                """
                SELECT t.id FROM tags t
                JOIN repositories r ON t.repository = r.id
                WHERE r.path = :repository_path AND t.name = :tag_name;
                """,
                repository_path=repository_path, tag_name=tag_name
            )

            if tag_error:
                logging.info(f"Error finding tag to unmark: {tag_error}")
                return

            # Check if tag exists
            if not tag_query_result:
                logging.info(f"No tag found for {repository_path} with name {tag_name} to unmark")
                return

            tag_id = tag_query_result[0][0]

            # Delete the mark for this tag.
            delete_mark_result, delete_mark_error = await conn.execute(
                """
                DELETE FROM marks
                WHERE tag_id = :tag_id AND mark = :mark_value;
                """,
                tag_id=tag_id, mark_value=mark.value
            )

            if delete_mark_error:
                logging.info(f"Error deleting mark from tag: {delete_mark_error}")
            else:
                logging.info(f"Mark deleted from tag {tag_name} for repository {repository_path}")

    async def get_all_repositories(self):
        async with await self.db.connection() as conn:
            (result, error) = await conn.query(
                'SELECT * FROM repositories'
            )
            return (result, error)


async def versioning_on_init(app):
    """Used to start up the version_manager"""
    app['version_manager'] = VersionManager(app['blade'])
    await app['version_manager'].set_up()
    try:
        await app['version_manager'].sync(cache=False)
    except:
        pass
