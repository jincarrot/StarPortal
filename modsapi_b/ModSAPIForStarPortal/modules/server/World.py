# # -*- coding: utf-8 -*-
from copy import deepcopy

import mod.server.extraServerApi as serverApi

from Entity import *
from Player import *
from WorldEvents import *
from Dimension import *
from Scoreboard import *
from ...interfaces.Game import *
from Container import *
# from .architect.scheduler import Scheduler
from managers.TickingAreaManager import *
from managers.StructureManager import *
# from decorators import *
from ...utils.system import systems
from ...utils.entity import queryEntities

ServerSystem = serverApi.GetServerSystemCls()
comp = serverApi.GetEngineCompFactory()

class World(ServerSystem):

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self.__afterEvents = WorldAfterEvents()
        self.__beforeEvents = WorldBeforeEvents()
        self.__gameRules = GameRules()
        self.__scoreboard = Scoreboard()
        self.__tickingAreaManager = TickingAreaManager()
        self.__structureManager = StructureManager()

    @property
    def levelId(self):
        """Runtime identifier of the current level."""
        return serverApi.GetLevelId()
    
    @property
    def afterEvents(self):
        return self.__afterEvents

    @property
    def beforeEvents(self):
        return self.__beforeEvents
    
    @property
    def levelId(self):
        """Runtime identifier of the current level."""
        return serverApi.GetLevelId()

    @property
    def gameRules(self):
        return self.__gameRules

    @property
    def scoreboard(self):
        return self.__scoreboard

    @property
    def tickingAreaManager(self):
        return self.__tickingAreaManager

    @property
    def structureManager(self):
        return self.__structureManager

    @staticmethod
    def getAllPlayers():
        playerIds = serverApi.GetPlayerList()
        players = []
        for playerId in playerIds:
            if playerId in systems.core.entities:
                player = systems.core.entities[systems.core.entities.index(playerId)]
                players.append(player)
            else:
                player = Player(playerId)
                systems.core.entities.append(player)
                players.append(player)
        return players

    @staticmethod
    def getPlayers(options={}):
        options['type'] = 'minecraft:player'
        return queryEntities(options)

    @staticmethod
    def getDimension(dimensionId):
        return Dimension(dimensionId)

    @staticmethod
    def setDynamicProperty(identifier, value):
        SComp.CreateExtraData(serverApi.GetLevelId()).SetExtraData(identifier, deepcopy(value))

    @staticmethod
    def getDynamicProperty(identifier):
        data = SComp.CreateExtraData(serverApi.GetLevelId()).GetExtraData(identifier)
        if isinstance(data, dict):
            return deepcopy(data)
        return data
    
    @staticmethod
    def getDynamicPropertyIds():
        data = SComp.CreateExtraData(serverApi.GetLevelId()).GetWholeExtraData()
        return data.keys()
    
    @staticmethod
    def getDynamicPropertyTotalByteCount():
        DataComp = SComp.CreateExtraData(serverApi.GetLevelId())
        data = DataComp.GetWholeExtraData()
        count = 0
        for key in data.keys():
            count += len(key)
            value = data[key]
            if type(value).__name__ == 'str':
                count += len(value)
            else:
                count += 8
        return count
    
    def getEntity(self, id):
        if id in systems.core.entities:
            return systems.core.entities[systems.core.entities.index(id)]
        
    @staticmethod
    def getTimeOfDay():
        return SComp.CreateTime(serverApi.GetLevelId()).GetTime() % 24000
    
    @staticmethod
    def getAbsoluteTime():
        return SComp.CreateTime(serverApi.GetLevelId()).GetTime()
    
    @staticmethod
    def setTimeOfDay(timeOfDay):
        SComp.CreateTime(serverApi.GetLevelId()).SetTimeOfDay(timeOfDay)

    @staticmethod
    def setAbsoluteTime(absoluteTime):
        SComp.CreateTime(serverApi.GetLevelId()).SetTime(absoluteTime)

    def __stopMusic(self):
        self.BroadcastToAllClient("setMusicState", {"state": False})

    def sendMessage(self, message):
        for player in self.getAllPlayers():
            player.sendMessage("[服务器]" + message)

    @staticmethod
    def getLootTableManager():
        return
    