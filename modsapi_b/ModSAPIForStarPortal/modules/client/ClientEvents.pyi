
from events.signals.SystemEventSignals import *

class ClientAfterEvents:
    """Client events of ModSAPI."""

    @property
    def serverEventReceive(self) -> ServerEventReceiveAfterEventSignal:
        """Event triggered when server sends data to client."""

    @property
    def serverRequestData(self) -> ServerRequestDataAfterEventSignal:
        """Event triggered when server requests data from client."""
    