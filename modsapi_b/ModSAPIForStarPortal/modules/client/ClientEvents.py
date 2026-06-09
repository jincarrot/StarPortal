# -*- coding: utf-8 -*-
from events.signals.SystemEventSignals import *

class ClientAfterEvents:
    """Client events of ModSAPI."""

    def __init__(self, clientSystem):
        self.__onServerSendToClient = ServerEventReceiveAfterEventSignal()
        self.__serverRequestData = ServerRequestDataAfterEventSignal()

    @property
    def serverEventReceive(self):
        """Event triggered when server sends data to client."""
        return self.__onServerSendToClient
    
    @property
    def serverRequestData(self):
        """Event triggered when server sends data to client and expect a response."""
        return self.__serverRequestData