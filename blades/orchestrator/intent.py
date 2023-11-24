
"""
# Intents.

Intents is an orchestration concept designed to manipulate the swarm.
They are designed a configuration rather than instructions. The goal is
configure different modules rather than specificly follow each instruction 
and centralize them.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar('T')
@dataclass
class Intent(Generic[T]):
    """
    Intents are wrapped to contain a host (they always are meant to an entity)
    """
    id: str                     # time:host
    host: str                   # including port
    blade: str                  # blade to use
    version: str                # blade's version
    params: T                   # defined by each orchestrations
