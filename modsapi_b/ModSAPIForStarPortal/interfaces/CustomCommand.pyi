# -*- coding: utf-8 -*-

from typing import TypedDict
from ..enums.CustomCommand import CustomCommandSource, CustomCommandStatus
from ..modules.server.Entity import Entity
from ..modules.server.Block import Block

class CustomCommand(TypedDict):
    """
    Define the custom command, including name, permissions, and parameters.   
    """
    name: str
    """The name of the command. A namespace is required."""

class CustomCommandResult(TypedDict):
    """The result of a custom command execution, which can be used to modify the command's behavior."""
    status: CustomCommandStatus
    """The status code of the command execution. A non-zero value typically indicates an error."""
    message: str
    """An optional message that can provide additional information about the command execution result."""

class CustomCommandOrigin:
    """Details about the origins of the command."""

    @property
    def initiator(self) -> Entity:
        """If this command was initiated via an NPC, returns the entity that initiated the NPC dialogue."""
    
    @property
    def sourceBlock(self) -> Block:
        """Source block if this command was triggered via a block (e.g., a commandblock.)"""
    
    @property
    def sourceEntity(self) -> Entity:
        """Source entity if this command was triggered by an entity (e.g., a NPC)."""
    
    @property
    def sourceType(self) -> CustomCommandSource:
        """Returns the type of source that fired this command."""
