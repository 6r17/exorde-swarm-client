import pytest
from blades.orchestrator.versioning import get_repository_versioning
from packaging import version
from datetime import datetime


@pytest.mark.asyncio
async def test_get_repository_versioning():
    repo = "exorde-labs/exorde-swarm-client"
    tags = await get_repository_versioning(repo)
    assert len(tags.tags_report) >= 1
