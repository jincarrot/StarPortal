# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi

ClientSystem = clientApi.GetClientSystemCls()

class DecoratorsClient(ClientSystem):
    """Contains all decorators of ModSAPI that run on the client."""

    @property
    def serverCallable(self):
        from .decorators import serverCallable
        return serverCallable
    