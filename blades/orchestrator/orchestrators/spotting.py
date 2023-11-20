def spotting_orchestration(blade, capabilities: dict[str, str], topology: dict) -> Intent:
    """The spotting orchestrator has no special implementation on static top"""
    return Intent(
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        blade='spotting', # we never change a blade's behavior in static top
        version=capabilities['exorde-labs/exorde-swarm-client'],
        host='{}:{}'.format(blade['host'], blade['port']),
        params=SpottingIntentParameters() # does nothing for spotting, maybe pass worker addr
    )
