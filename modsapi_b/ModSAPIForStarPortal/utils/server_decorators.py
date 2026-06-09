# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi

ServerSystem = serverApi.GetServerSystemCls()

class DecoratorsServer(ServerSystem):
    """Contains all decorators of ModSAPI that run on the server."""

    @property
    def clientCallable(self):
        from .decorators import clientCallable
        return clientCallable
    