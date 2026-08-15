# -*- coding: utf-8 -*-

class CustomCommand(object):
    """
    Define the custom command, including name, permissions, and parameters.   
    """

    def __init__(self, data):
        self.name = data['name']

class CustomCommandOrigin:
    """Details about the origins of the command."""

    def __init__(self, data):
        self.__initiator = data.get('initiator', None)
        self.__sourceBlock = data.get('sourceBlock', None)
        self.__sourceEntity = data.get('sourceEntity', None)
        self.__sourceType = data.get('sourceType', None)

    @property
    def initiator(self):
        """If this command was initiated via an NPC, returns the entity that initiated the NPC dialogue."""
        return self.__initiator
    
    @property
    def sourceBlock(self):
        """Source block if this command was triggered via a block (e.g., a commandblock.)"""
        return self.__sourceBlock
    
    @property
    def sourceEntity(self):
        """Source entity if this command was triggered by an entity (e.g., a NPC)."""
        return self.__sourceEntity
    
    @property
    def sourceType(self):
        """Returns the type of source that fired this command."""
        return self.__sourceType
    
class CustomCommandResult:
    """The result of a custom command execution, which can be used to modify the command's behavior."""

    def __init__(self, data):
        self.status = data.get('status', 0)
        self.message = data.get('message', "")
