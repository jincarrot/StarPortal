# -*- coding: utf-8 -*-
from ..config import Namespace

def serverCallable(func):
    """Registers a function as callable from the client. The function can then be called from the client using client.system.runServerFunc(funcName, *args, **kwargs), where funcName is the name of the function on the server."""

def clientCallable(func):
    """Registers a function as callable from the server. The function can then be called from the server using server.system.runClientFunc(player, funcName, *args, **kwargs), where funcName is the name of the function on the client."""
    