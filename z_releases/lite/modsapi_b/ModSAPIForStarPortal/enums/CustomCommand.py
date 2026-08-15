# -*- coding: utf-8 -*-

class CustomCommandSource:
    """Who executed the command."""

    Block = "Block"
    """Command originated from a command block."""
    Entity = "Entity"
    """Command originated from an entity."""
    NPCDialogue = "NPCDialogue"
    """Command originated from an NPC dialogue."""
    Server = "Server"
    """Command originated from the server."""

class CustomCommandStatus:
    """Status codes for custom command execution results."""

    Success = 0
    """Command executed successfully."""
    Failed = 1
    """Command execution failed due to an error."""
    