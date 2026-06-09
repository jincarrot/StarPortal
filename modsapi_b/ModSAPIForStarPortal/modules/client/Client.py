# -*- coding: utf-8 -*-
import math, random
import mod.client.extraClientApi as clientApi
from ClientEvents import *
from Player import *
from Screen import Screen
from Entity import ClientEntity
from Audio import Audio
from Particle import Particle
from DynamicParticle import DynamicParticle
from ...interfaces.Vector import Vector3
from ...interfaces.ParticleOptions import DynamicParticleOptions, DynamicParticlePattern
from ...utils.promise import Promise

ClientSystem = clientApi.GetClientSystemCls()
CComp = clientApi.GetEngineCompFactory()

class Client(ClientSystem):
    """Client system of ModSAPI"""

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.__localPlayer = ClientPlayer()
        self.__afterEvents = ClientAfterEvents(self)
        self.__screen = Screen()
        self.__audio = Audio()

    @property
    def levelId(self):
        """Runtime identifier of the current level."""
        return clientApi.GetLevelId()
    
    @property
    def localPlayer(self):
        """The local player."""
        return self.__localPlayer

    @property
    def afterEvents(self):
        """Contains a set of events that are applicable to the entirety of this client side.
        Event callbacks are called in a deferred manner.
        Event callbacks are executed in read-write mode."""
        return self.__afterEvents

    @property
    def screen(self):
        """Contains informations of player's screen."""
        return self.__screen
    
    @property
    def audio(self):
        """Contains operations related to audio."""
        return self.__audio

    def sendToServer(self, eventName, data):
        """Sends data to server. Server can listen to this data by subscribing to the event with the same name."""
        self.NotifyToServer("clientSendToServer", {"eventName": eventName, "data": data})

    def getDataFromServer(self, dataName, data=None):
        idx = random.randint(0, 999999)
        promise = Promise()
        self.sendToServer("getData:" + dataName, {"id": idx,"data": data})
        def processReturnedData(returnedData):
            promise._run(returnedData.data)
        self.afterEvents.serverEventReceive.subscribe("getDataSuccess:" + str(idx), processReturnedData)
        return promise
    
    def runServerFunc(self, funcName, *args, **kwargs):
        return self.getDataFromServer("runServerFunc", {"funcName": funcName, "args": args, "kwargs": kwargs})
    
    def getEntity(self, entityId):
        """Gets an entity by its runtime identifier."""
        entity = ClientEntity(entityId)
        if not entity.isValid:
            return entity
        
    def spawnEntity(self, typeId, location):
        """
        Spawns a client-side entity of the given type at the given location. 
        Returns the runtime identifier of the spawned entity.
        """
        return self.getEntity(self.CreateClientEntityByTypeStr(typeId, location.getTuple(), (0, 0)))
    
    def spawnParticle(self, typeId, location, options={}):
        """Spawns a particle effect."""
        location = Vector3(location)
        parId = CComp.CreateParticleSystem(clientApi.GetLevelId()).Create(typeId, location.getTuple())
        return Particle(parId)

    def spawnDynamicParticle(self, pattern, location, options={}):
        # type: (DynamicParticlePattern, Vector3, DynamicParticleOptions) -> None
        """创建一个表达式粒子，能够通过数学表达式动态的绘制图案。"""
        return DynamicParticle(pattern, location, options)

