# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
from ....config import Namespace

class ProtectedEntityRegistry:
    """Registry for protected entities. Protected entities are entities that cannot be killed by commands."""

    def register(self, typeId, condition=lambda entity: True):
        """Registers a protected entity type."""
        coreSystem = serverApi.GetSystem(Namespace, "core")
        pass
