
import time

from ..intent import Intent
from dataclasses import dataclass

@dataclass
class OrchestratorIntentParameters:
    """Does-Nothing"""
    pass

async def orchestrator_orchestration(blade, capabilities: dict[str, str], __topology__: dict, __selfblade__) -> Intent:
    """The orchestrator orchestrator has no special implementation on static top"""
    return Intent(
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        blade='orchestrator',
        version=capabilities['exorde-labs/exorde-swarm-client'],
        host='{}:{}'.format(blade['host'], blade['port']),
        params=OrchestratorIntentParameters() # does nothing for orch,  NOTE : both need to control
                                                                              # version
    )
