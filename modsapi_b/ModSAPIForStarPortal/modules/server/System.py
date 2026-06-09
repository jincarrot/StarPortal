# -*- coding: utf-8 -*-
from ...architect.scheduler import Scheduler
import mod.server.extraServerApi as serverApi
from SystemEvents import SystemAfterEvents, SystemBeforeEvents
from ...utils.promise import Promise
import random
from ...config import Namespace

ServerSystem = serverApi.GetServerSystemCls()

class System(ServerSystem):
    """
    A class that provides system-level events and functions.
    """

    # _scriptScheduler = Scheduler()

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        # self._initScheduler()
        self.__afterEvents = SystemAfterEvents()
        self.__beforeEvents = SystemBeforeEvents()
        self.__timers = {}
        self.__timerId = 0
        self.__comp = serverApi.GetEngineCompFactory().CreateGame(serverApi.GetLevelId())
        self.__exportedFunctions = {}

    @property
    def beforeEvents(self):
        return self.__beforeEvents
    
    @property
    def afterEvents(self):
        """Returns a collection of after-events for system-level operations."""
        return self.__afterEvents
    
    def _OnScriptTickServer(self):
        self._scriptScheduler.executeSequenceAsync()

    def _initScheduler(self):
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "OnScriptTickServer",
            self,
            self._OnScriptTickServer
        )

    def run(self, callback):
        """
        Runs a specified function at the next available future time. 
        This is frequently used to implement delayed behaviors and game loops. 
        When run within the context of an event handler, this will generally run the code at the end of the same tick where the event occurred. 
        When run in other code (a system.run callout), this will run the function in the next tick. 
        
        Note, however, that depending on load on the system, running in the same or next tick is not guaranteed."""
        self.__timers[self.__timerId] = self.__comp.AddTimer(0.05, callback)
        self.__timerId += 1
        return self.__timerId - 1

    def runTimeout(self, callback, tickDelay=1):
        """
        Runs a set of code at a future time specified by tickDelay.
        """
        self.__timers[self.__timerId] = self.__comp.AddTimer(0.05 * tickDelay, callback)
        self.__timerId += 1
        return self.__timerId - 1

    def runInterval(self, callback, tickInterval=1):
        """
        Runs a set of code on an interval.
        """
        self.__timers[self.__timerId] = self.__comp.AddRepeatedTimer(0.05 * tickInterval, callback)
        self.__timerId += 1
        return self.__timerId - 1

    def clearRun(self, runId):
        """
        Cancels the execution of a function run that was previously scheduled via @minecraft/server.System.run.
        """
        if runId not in self.__timers:
            return
        self.__comp.CancelTimer(self.__timers[runId])
        del self.__timers[runId]

    def sendToClient(self, player, eventName, data=None):
        """Send data to client."""
        from ..server.Player import Player
        players = []
        if isinstance(player, (list, tuple)):
            for p in player:
                if isinstance(p, Player):
                    players.append(p.id)
                else:
                    players.append(p)
        elif isinstance(player, Player):
            players.append(player.id)
        else:
            players.append(player)
        if len(players) == 1:
            self.NotifyToClient(players[0], "serverSendToClient", {"eventName": eventName, "data": data})
        else:
            self.NotifyToMultiClients(players, "serverSendToClient", {"eventName": eventName, "data": data})

    def sendToAllClients(self, eventName, data):
        """Send data to all clients."""
        self.BroadcastToAllClient("serverSendToClient", {"eventName": eventName, "data": data})

    def getDataFromClient(self, player, dataName, data=None):
        if isinstance(player, list):
            raise TypeError("player should be a Player | str, but got list.")
        idx = random.randint(0, 999999)
        promise = Promise()
        self.sendToClient(player, "getData:" + dataName, {"id": idx, "data": data})
        def processReturnedData(returnedData):
            promise._run(returnedData.data)
        self.afterEvents.clientEventReceive.subscribe("getDataSuccess:" + str(idx), processReturnedData)
        return promise
    
    def runClientFunc(self, player, funcName, *args, **kwargs):
        return self.getDataFromClient(player, "runClientFunc", {"funcName": funcName, "args": args, "kwargs": kwargs})

    def runJob(self, generator):
        return self._scriptScheduler.addSuspendableTask('SchedulerTask', generator)
    
    def clearJob(self, jobId):
        self.clearRun(jobId)

    def exportFunc(self, identifier, callback):
        """Exports a function that can be called from other systems or modules."""
        self.__exportedFunctions[identifier] = callback

    def importFunc(self, identifier):
        """Imports a function that was exported by another system or module."""
        return self.__exportedFunctions.get(identifier, None)