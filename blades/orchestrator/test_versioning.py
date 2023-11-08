import pytest
from blades.orchestrator.versioning import get_repository_versioning, VersionManager, Mark
from packaging import version
from datetime import datetime
import os

@pytest.mark.asyncio
async def test_version_manager():
    """
    Test the version-manager by :
        instanciating it
        synching it up
        marking a tag as deffective
        retrieving working latest repo/tags combs
        checking the count differences
        
    """
    version_manager = VersionManager({
        'static_cluster_parameters': {
            'scrapers': [
                "exorde-labs/exorde-scraping-module"
            ],
            'database_provider': 'sqlite',
            'db': {
                'driver': 'sqlite',
                'database': 'test_database.sqlite'
            }
        }
    })

    await version_manager.set_up()
    await version_manager.sync(cache=False)
    repositories = await version_manager.get_all_repositories()
    working_tagged_repositories = await version_manager.get_latest_valid_tags_for_all_repos()
    some_tag = working_tagged_repositories[0]
    mark = await version_manager.mark_tag_as(
        some_tag.tag_name, some_tag.repository_path, Mark.DEFFECTIVE
    )
    working_tagged_repositories_after_mark = await version_manager.get_latest_valid_tags_for_all_repos()
    assert len(working_tagged_repositories) > len(
        working_tagged_repositories_after_mark
    )
    await version_manager.delete_mark_from_tag(
        some_tag.tag_name, some_tag.repository_path, Mark.DEFFECTIVE
    )
    working_tagged_repositories_after_deleted_mark = await version_manager.get_latest_valid_tags_for_all_repos()
    assert len(working_tagged_repositories) == len(
        working_tagged_repositories_after_deleted_mark
    )
