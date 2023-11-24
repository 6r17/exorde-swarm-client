from ..intent import Intent
import time

from dataclasses import dataclass

@dataclass
class SpottingIntentParameters:
    """
    For now there is no specific configuration around the Spotting module
    because it's main_address is configured trough config which is sufficient 
    for static topology.
    """
    pass

async def spotting_orchestration(blade, capabilities: dict[str, str], __topology__: dict, __selfblade__) -> Intent:
    """The spotting orchestrator has no special implementation on static top"""
    return Intent(
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        blade='spotting', # we never change a blade's behavior in static top
        version=capabilities['exorde-labs/exorde-swarm-client'],
        host='{}:{}'.format(blade['host'], blade['port']),
        params=SpottingIntentParameters() # does nothing for spotting, maybe pass worker addr
    )
