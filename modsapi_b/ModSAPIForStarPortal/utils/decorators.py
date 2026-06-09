# -*- coding: utf-8 -*-
from ..config import Namespace

def serverCallable(func):
    """Registers a function as callable from the client. The function can then be called from the client using client.system.runServerFunc(funcName, *args, **kwargs), where funcName is the name of the function on the server."""
    import mod.client.extraClientApi as clientApi
    client = clientApi.GetSystem(Namespace, "client_core")
    client.serverCallableFunctions[func.__name__] = func

def clientCallable(func):
    """Registers a function as callable from the server. The function can then be called from the server using server.system.runClientFunc(player, funcName, *args, **kwargs), where funcName is the name of the function on the client."""
    import mod.server.extraServerApi as serverApi
    server = serverApi.GetSystem(Namespace, "core")
    server.clientCallableFunctions[func.__name__] = func
    