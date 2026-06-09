# -*- coding: utf-8 -*-
from typing import Callable, Any
from ..EventBases import *
from ..core.SystemEvents import *

class ServerEventReceiveAfterEventSignal(Events):
    """
    Triggers when use ModSAPI.server.system.sendToClient.
    """

    def _check(self, obj, data, valueName):
        # type: (EventListener, dict, str) -> bool
        pass

    def subscribe(self, eventName, callback, options={}):
        # type: (str, Callable[[ServerEventReceiveAfterEvent], None], dict) -> None
        """
        Registers a new ScriptEvent handler.
        """

class ServerRequestDataAfterEventSignal(Events):
    """
    Allows for registering an event handler that responds to inbound /scriptevent commands.
    """

    def subscribe(self, eventName: str, callback: Callable[[], Any], options={}):
        """"""
