# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
from ....config import Namespace

class ProtectedEntityRegistry:

    def __init__(self):
        pass

    def register(self, typeId, condition=lambda entity: True):
        coreSystem = serverApi.GetSystem(Namespace, "core")
        coreSystem.protectedEntityTypes[typeId] = condition
