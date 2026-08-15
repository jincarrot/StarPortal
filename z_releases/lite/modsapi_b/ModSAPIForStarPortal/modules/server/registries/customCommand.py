# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
from ....config import Namespace

class CustomCommandRegistry:

    def __init__(self):
        pass

    def registerCommand(self, customCommand, callback):
        coreSystem = serverApi.GetSystem(Namespace, "core")
        name = customCommand['name']
        coreSystem.customCommands[name] = callback
