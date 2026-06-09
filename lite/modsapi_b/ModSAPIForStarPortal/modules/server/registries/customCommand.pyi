# -*- coding: utf-8 -*-
from ....interfaces.CustomCommand import CustomCommand, CustomCommandOrigin, CustomCommandResult
from typing import Callable

class CustomCommandRegistry:
    """Provides the functionality for registering custom commands."""

    def registerCommand(self, customCommand: CustomCommand, callback: Callable[[CustomCommandOrigin, list], None | CustomCommandResult]):
        """
        Registers a custom command that when executed triggers a script callback.
        
        Note: parameter customCommand has no effect. You need to define custom commands in folder 'netease_commands'.
        """
