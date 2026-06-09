# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi
from system import systems
from ..modules.server.Entity import *
from ..enums.CustomCommand import CustomCommandSource
from ..interfaces.CustomCommand import CustomCommandOrigin

ServerSystem = serverApi.GetServerSystemCls()
comp = serverApi.GetEngineCompFactory()

class CoreSystem(ServerSystem):
    
    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self.protectedEntityTypes = {}
        self.entities = []
        self.customCommands = {}
        self.clientCallableFunctions = {}
        systems.system.afterEvents.clientRequestData.subscribe("runServerFunc", self.runServerFunc)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "GlobalCommandServerEvent", self, self.commandHandler)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "AddEntityServerEvent", self, self.addEntity)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "AddServerPlayerEvent", self, self.addEntity)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "EntityRemoveEvent", self, self.removeEntity)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "ChunkAcquireDiscardedServerEvent", self, self.removeEntity)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(), "CustomCommandTriggerServerEvent", self, self.customCommandHandler)

    def runServerFunc(self, data):
        data = data.data
        funcName = data['funcName']
        args = data['args']
        kwargs = data['kwargs']
        if funcName in self.clientCallableFunctions:
            result = self.clientCallableFunctions[funcName](*args, **kwargs)
            return result
    def setScoreboard(self, playerName, objective, score):
        scoreboard = systems.world.getDynamicProperty("scoreboard.%s" % objective)
        if not scoreboard:
            scoreboard = {}
        scoreboard[playerName] = score
        systems.world.setDynamicProperty("scoreboard.%s" % objective, scoreboard)

    def getScoreboard(self, playerName, objective):
        scoreboard = systems.world.getDynamicProperty("scoreboard.%s" % objective)
        if not scoreboard:
            return 0
        return scoreboard.get(playerName, 0)

    def commandHandler(self, data):
        if 'scoreboard' in data['command']:
            """scoreboard players [set | add | remove] <player: target> <objective: string> <count: int>"""
            params = data['command'].split('scoreboard')[1].split(" ")
            del params[0]
            if params[0] == 'players':
                if params[1] in ['set', 'add', 'remove']:
                    objective = params[3]
                    count = int(params[4])
                    if "@" in params[2]:
                        players = comp.CreateEntityComponent(data['entityId']).GetEntitiesBySelector(params[2])
                        for player in players:
                            if systems.world.getEntity(player).typeId == "minecraft:player":
                                player = systems.world.getEntity(player).nameTag
                            if params[1] == 'set':
                                self.setScoreboard(player, objective, count)
                            elif params[1] == 'add':
                                self.setScoreboard(player, objective, self.getScoreboard(player, objective) + count)
                            elif params[1] == 'remove':
                                self.setScoreboard(player, objective, self.getScoreboard(player, objective) - count)
                        return
                    player = params[2]
                    if params[1] == 'set':
                        self.setScoreboard(player, objective, count)
                    elif params[1] == 'add':
                        self.setScoreboard(player, objective, self.getScoreboard(player, objective) + count)
                    elif params[1] == 'remove':
                        self.setScoreboard(player, objective, self.getScoreboard(player, objective) - count)
        elif "kill" in data['command']:
            """kill <target: target>"""
            pass
    def addEntity(self, data):
        if data['id'] not in self.entities:
            self.entities.append(createEntity(data['id']))

    def removeEntity(self, data):
        if 'entities' in data:
            for entityId in data['entities']:
                if entityId in self.entities:
                    self.entities.remove(entityId)
        else:
            if data['id'] in self.entities:
                self.entities.remove(data['id'])

    def customCommandHandler(self, data):
        name = data['command']
        if name in self.customCommands:
            sourceData = data['origin']
            source = None
            sourceType = CustomCommandSource.Server
            if sourceData.get('entityId', None):
                source = createEntity(sourceData['entityId'])
                sourceType = CustomCommandSource.Entity
                if source.typeId == 'minecraft:npc':
                    sourceType = CustomCommandSource.NPCDialogue
            else:
                source = Block({"dimension": Dimension(sourceData['dimension']), "location": Vector3(sourceData['blockPos'])})
                sourceType = CustomCommandSource.Block
            argData = {
                "sourceType": sourceType
            }
            if sourceType == CustomCommandSource.Entity:
                argData['sourceEntity'] = source
            elif sourceType == CustomCommandSource.Block:
                argData['sourceBlock'] = source
            elif sourceType == CustomCommandSource.NPCDialogue:
                argData['initiator'] = source
            result = self.customCommands[name](CustomCommandOrigin(argData), data['args'])
            if result:
                data['return_failed'] = result['status'] != 0
                data['return_msg_key'] = result['message']

