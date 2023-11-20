def orchestrator_orchestration(blade, capabilities: dict[str, str], topology: dict) -> Intent:
    """The orchestrator orchestrator has no special implementation on static top"""
    return Intent(
        id='{}:{}:{}'.format(time.time(), blade['host'], blade['port']),
        blade='orchestrator',
        version=capabilities['exorde-labs/exorde-swarm-client'],
        host='{}:{}'.format(blade['host'], blade['port']),
        params=OrchestratorIntentParameters() # does nothing for orch,  NOTE : both need to control
                                                                              # version
    )
