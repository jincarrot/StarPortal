# -*- coding: utf-8 -*-
from ModSAPI.client.beta import *
import mod.client.extraClientApi as clientApi

PausedParticles = [] # type: list[Particle]
StarRegionParticles = []
PortalId = None

def spawnStarLine(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    data = arg.data
    particle = client.spawnParticle("elspirit:star_line", data['location'])
    for molang in data['molang']:
        particle.setMolang("variable.%s" % molang, data['molang'][molang])
    clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId()).AddTimer(5, particle.pause)
    PausedParticles.append(particle)

client.afterEvents.serverEventReceive.subscribe("spawnStarLine", spawnStarLine)

def spawnStarRegion(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    global PortalId
    PortalId = arg.data['portalId']
    location = arg.data['location']
    for pIndex in range(4):
        particle = client.spawnParticle("elspirit:star_region_start_%s" % pIndex, location)
        clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId()).AddTimer(5, particle.pause)
        StarRegionParticles.append(particle)
    client.audio.playSound("star.gain", {"location": location})
    client.audio.playSound("star.waiting", {"location": location})

client.afterEvents.serverEventReceive.subscribe("spawnStarRegion", spawnStarRegion)

def stopInteraction(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    global PausedParticles
    global StarRegionParticles
    client.spawnParticle("elspirit:star_region_end", StarRegionParticles[0].location)
    for particle in StarRegionParticles:
        particle.remove()
    StarRegionParticles = []
    for particle in PausedParticles:
        particle.remove()
    PausedParticles = []

client.afterEvents.serverEventReceive.subscribe("stopInteraction", stopInteraction)

class HudProxy(clientApi.GetUIScreenProxyCls()):

    def OnCreate(self):
        self.screen = self.GetScreenNode() # type: clientApi.ScreenNode
        self.manage_btn = self.screen.GetBaseUIControl("/variables_button_mappings_and_controls/safezone_screen_matrix/inner_matrix/safezone_screen_panel/root_screen_panel/root_panel/manage_btn").asButton()
        self.manage_btn.AddTouchEventParams({"isSwallow": True})
        self.manage_btn.SetButtonTouchUpCallback(self.onClickManageBtn)
        self.hideBtn(None)
        client.afterEvents.serverEventReceive.subscribe("spawnStarRegion", self.showBtn)
        client.afterEvents.serverEventReceive.subscribe("stopInteraction", self.hideBtn)
    
    def showBtn(self, arg):
        if arg.data.get("shouldShowManager", False):
            self.manage_btn.SetVisible(True)

    def hideBtn(self, arg):
        self.manage_btn.SetVisible(False)

    def onClickManageBtn(self, data):
        client.sendToServer("openStarPortalManager", {"playerId": client.localPlayer.id, "portalId": PortalId})

clientApi.GetNativeScreenManagerCls().instance().RegisterScreenProxy('hud.hud_screen', "Scripts_StarPortal.client.HudProxy")

def hideNode(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    entityId = arg.data
    comp = clientApi.GetEngineCompFactory()
    comp.CreateGame(clientApi.GetLevelId()).AddTimer(0.05, comp.CreateActorRender(entityId).SetNotRenderAtAll, True)

client.afterEvents.serverEventReceive.subscribe("hideNode", hideNode)

def onTeleport(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    client.audio.playSound("star.flyto", {"location": arg.data})
    client.spawnParticle("elspirit:teleport_light", arg.data)

client.afterEvents.serverEventReceive.subscribe("teleport", onTeleport)

def onTeleportEnd(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    client.audio.playSound("spirit.gain", {"location": arg.data})
    client.spawnParticle("elspirit:teleport_end", arg.data)
    client.spawnParticle("sl:dialog_pre", arg.data)

client.afterEvents.serverEventReceive.subscribe("teleportEnd", onTeleportEnd)
