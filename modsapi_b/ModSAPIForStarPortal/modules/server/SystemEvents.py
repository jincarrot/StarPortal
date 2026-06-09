# -*- coding: utf-8 -*-
# from typing import Union, Dict

from .events.signals.WorldEventSignals import *

import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi

SComp = serverApi.GetEngineCompFactory()
CComp = clientApi.GetEngineCompFactory()


class SystemAfterEvents(object):
    """
    Provides a set of events that fire within the broader scripting system within Minecraft.
    """

    def __init__(self):
        self.__scriptEventReceive = ScriptEventCommandMessageAfterEventSignal()
        self.__clientEventReceive = ClientEventReceiveAfterEventSignal()
        self.__clientRequestData = ClientRequestDataAfterEventSignal()

    @property
    def scriptEventReceive(self):
        """Fires when a script event is received. This includes events sent by both the client and the server."""
        return self.__scriptEventReceive
    
    @property
    def clientEventReceive(self):
        return self.__clientEventReceive
    
    @property
    def clientRequestData(self):
        return ClientRequestDataAfterEventSignal()

class SystemBeforeEvents:
    """
    A set of events that fire before an actual action occurs. 
    
    In most cases, you can potentially cancel or modify the impending event. 
    
    Note that in before events any APIs that modify gameplay state will not function and will throw an error.
    """

    def __init__(self):
        self.__startup = StartupBeforeEventSignal()

    @property
    def startup(self):
        return self.__startup
