# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from ..config import Namespace

class Systems:

    _client = None
    _decorators = None

    @property
    def client(self):
        if self._client:
            return self._client
        client = clientApi.GetSystem(Namespace, "client")
        self._client = client
        return client
    
    @property
    def decorators(self):
        if self._decorators:
            return self._decorators
        decorators = clientApi.GetSystem(Namespace, "client_decorators")
        self._decorators = decorators
        return decorators


systems = Systems()