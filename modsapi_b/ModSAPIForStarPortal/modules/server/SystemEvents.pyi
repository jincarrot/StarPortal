# -*- coding: utf-8 -*-
# from typing import Union, Dict

from .events.signals.WorldEventSignals import *

class SystemAfterEvents(object):
    """
    Provides a set of events that fire within the broader scripting system within Minecraft.
    """

    @property
    def scriptEventReceive(self) -> ScriptEventCommandMessageAfterEventSignal:
        """Fires when a script event is received. This includes events sent by both the client and the server."""
    
    @property
    def clientEventReceive(self) -> ClientEventReceiveAfterEventSignal: ...

    @property
    def clientRequestData(self) -> ClientRequestDataAfterEventSignal: ...

class SystemBeforeEvents:
    """
    A set of events that fire before an actual action occurs. 
    
    In most cases, you can potentially cancel or modify the impending event. 
    
    Note that in before events any APIs that modify gameplay state will not function and will throw an error.
    """

    @property
    def startup(self) -> StartupBeforeEventSignal:
        """"""