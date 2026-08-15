# -*- coding: utf-8 -*-
import math
from ModSAPI.client.beta import *
import mod.client.extraClientApi as clientApi
from FormUI.register import *

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
    client.audio.playSound("dialog.show", {"location": location})

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


# ============================================================
# 星图（星塔星座地图）界面
# ============================================================
StarMapNamespace = "Scripts_StarPortal"
StarMapUIKey = "star_map_ui"
StarMapScreenDef = "star_map.main"
StarMapClsPath = "Scripts_StarPortal.client.StarMapScreen"
StarMapData = {"portals": [], "center": [0, 0]}
_starMapRegistered = [False]

# 星塔颜色值(0-6) -> 图标着色RGB，与服务端 colors 列表顺序对应
StarColorRGB = {
    0: (0.35, 0.55, 1.0),   # 蓝
    1: (1.0, 0.35, 0.35),   # 红
    2: (0.35, 1.0, 0.45),   # 绿
    3: (1.0, 0.9, 0.35),    # 黄
    4: (0.8, 0.55, 1.0),    # 浅紫
    5: (0.55, 0.9, 1.0),    # 浅蓝
    6: (0.5, 0.5, 0.6),     # 黑(提亮以便在深色背景可见)
}

ScreenNodeCls = clientApi.GetScreenNodeCls()


class StarMapScreen(ScreenNodeCls):
    """微缩星塔星座地图。根据服务端下发的星塔数据，将星塔以 (x, z) 俯视投影
    成一张可拖动、可缩放的星座图，点击水晶图标弹出传送条。"""

    def __init__(self, namespace, name, param):
        ScreenNodeCls.__init__(self, namespace, name, param)
        self.window = None
        self.container = None
        self.zoom = 1.0
        self.minZoom = 0.02
        self.maxZoom = 16.0
        self.halfW = 160.0
        self.halfH = 88.0
        self.selected = None
        self.portalById = {}
        self.edges = []  # [(childId, parentId)]，星座连线对应的网络父子边

    # ---------- 生命周期 ----------
    def Create(self):
        self.window = self.GetBaseUIControl("/window")
        if not self.window:
            print("[StarMap] 找不到 /window 控件，请用UI调试工具确认根路径")
            return
        viewport = self.window.GetChildByPath("/viewport")
        self.container = self.window.GetChildByPath("/viewport/star_container")
        if viewport:
            size = viewport.GetSize()
            if size:
                self.halfW = size[0] / 2.0
                self.halfH = size[1] / 2.0
        # 窗口拖动与地图平移由 JSON 中 input_panel 的 draggable 属性原生处理，无需在此绑定。
        self._bind("/side_panel/btn_close", up=self.onClose)
        self._bind("/side_panel/btn_zoom_in", up=self.onZoomIn)
        self._bind("/side_panel/btn_zoom_out", up=self.onZoomOut)
        self._bind("/teleport_bar/tp_btn", up=self.onTeleport)
        self._bind("/teleport_bar/tp_close", up=self.onHidePopup)
        self._autoFit()
        self.buildCrystals()
        self.buildLines()
        self.layout()

    # ---------- 工具 ----------
    def _getBtn(self, relPath):
        ctrl = self.window.GetChildByPath(relPath)
        return ctrl.asButton() if ctrl else None

    def _bind(self, relPath, down=None, move=None, up=None, cancel=None):
        btn = self._getBtn(relPath)
        if not btn:
            print("[StarMap] 找不到按钮: %s" % relPath)
            return
        btn.AddTouchEventParams({"isSwallow": True})
        if down:
            btn.SetButtonTouchDownCallback(down)
        if move:
            btn.SetButtonTouchMoveCallback(move)
        if up:
            btn.SetButtonTouchUpCallback(up)
        if cancel:
            btn.SetButtonTouchCancelCallback(cancel)

    def _autoFit(self):
        """根据所有星塔的坐标范围自动选取一个初始缩放，使其大致铺满视口。"""
        portals = StarMapData.get("portals", [])
        center = StarMapData.get("center", [0, 0])
        cx, cz = center[0], center[1]
        maxR = 1.0
        for p in portals:
            loc = p['location']
            r = max(abs(loc[0] - cx), abs(loc[2] - cz))
            if r > maxR:
                maxR = r
        # 让最远的星塔落在视口约 80% 半径处
        fit = (min(self.halfW, self.halfH) * 0.8) / maxR
        self.zoom = max(self.minZoom, min(self.maxZoom, fit))

    # ---------- 构建 ----------
    def buildCrystals(self):
        self.portalById = {}
        if not self.container:
            return
        for portal in StarMapData.get("portals", []):
            pid = portal['id']
            self.portalById[pid] = portal
            ctrl = self.CreateChildControl("star_map.crystal_btn", "crystal_%d" % pid, self.container)
            if not ctrl:
                continue
            icon = ctrl.GetChildByName("icon").asImage()
            if icon:
                icon.SetSprite("textures/items/%s" % ("sub_portal" if portal.get('type') == 'sub' else "core_portal"))
                icon.SetSpriteColor(StarColorRGB.get(portal.get('color', 0), (1.0, 1.0, 1.0)))
            label = ctrl.GetChildByName("name").asLabel()
            if label:
                label.SetText(portal.get('name', ''))
            btn = ctrl.asButton()
            if btn:
                btn.AddTouchEventParams({"isSwallow": True})
                btn.SetButtonTouchUpCallback(self.onCrystalClick)

    def buildLines(self):
        """为每条"星塔 -> 其父星塔"的网络连接创建一条白色线段。枢纽星塔可能有
        多个父，故为每个可见的父各画一条。线段角度只与两点相对方位有关、与缩放
        无关，因此只在创建时旋转一次，之后缩放/重布局只更新长度与位置。"""
        self.edges = []
        if not self.container:
            return
        for portal in StarMapData.get("portals", []):
            parentIds = portal.get("parentIds")
            if not parentIds:
                single = portal.get("parentId", 0)
                parentIds = [single] if single else []
            for parentId in parentIds:
                parent = self.portalById.get(parentId)
                if not parent:
                    continue
                name = "line_%d_%d" % (portal['id'], parentId)
                ctrl = self.CreateChildControl("star_map.link_line", name, self.container)
                if not ctrl:
                    continue
                img = ctrl.asImage()
                if img:
                    img.SetSpriteColor((1.0, 1.0, 1.0))
                    dx = portal['location'][0] - parent['location'][0]
                    dz = portal['location'][2] - parent['location'][2]
                    # 屏幕Y向下，与世界Z同向映射，故直接用 atan2(dz, dx)
                    img.Rotate(math.degrees(math.atan2(dz, dx)))
                self.edges.append((portal['id'], parentId))

    def _portalPos(self, portal):
        center = StarMapData.get("center", [0, 0])
        loc = portal['location']
        return (self.halfW + (loc[0] - center[0]) * self.zoom,
                self.halfH + (loc[2] - center[1]) * self.zoom)

    def layout(self):
        if not self.container:
            return
        # 先排连线（在水晶之下），再排水晶
        for childId, parentId in self.edges:
            line = self.container.GetChildByName("line_%d_%d" % (childId, parentId))
            child = self.portalById.get(childId)
            parent = self.portalById.get(parentId)
            if not line or not child or not parent:
                continue
            x1, y1 = self._portalPos(child)
            x2, y2 = self._portalPos(parent)
            length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            line.SetPosition(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
            line.SetSize((max(1.0, length), 2))
        for pid, portal in self.portalById.items():
            ctrl = self.container.GetChildByName("crystal_%d" % pid)
            if not ctrl:
                continue
            px, py = self._portalPos(portal)
            ctrl.SetPosition((px, py))

    # ---------- 水晶点击 ----------
    def onCrystalClick(self, args):
        seg = (args.get("ButtonPath", "") if isinstance(args, dict) else "").split("/")[-1]
        if not seg.startswith("crystal_"):
            return
        try:
            pid = int(seg[len("crystal_"):])
        except ValueError:
            return
        portal = self.portalById.get(pid)
        if not portal:
            return
        self.selected = pid
        bar = self.window.GetChildByPath("teleport_bar")
        if bar:
            nameCtrl = bar.GetChildByName("tp_name")
            if nameCtrl:
                loc = portal['location']
                nameCtrl.SetText("%s  §7(%d, %d, %d)" % (portal.get('name', ''), int(loc[0]), int(loc[1]), int(loc[2])))
            bar.SetVisible(True)

    def onHidePopup(self, args):
        bar = self.window.GetChildByPath("teleport_bar")
        if bar:
            bar.SetVisible(False)
        self.selected = None

    def onTeleport(self, args):
        if self.selected is None:
            return
        client.sendToServer("starMapTeleport", {"playerId": client.localPlayer.id, "portalId": self.selected})
        clientApi.PopScreen()

    def onClose(self, args):
        clientApi.PopScreen()

    # ---------- 缩放 ----------
    def onZoomIn(self, args):
        self.zoom = min(self.maxZoom, self.zoom * 1.3)
        self.layout()

    def onZoomOut(self, args):
        self.zoom = max(self.minZoom, self.zoom / 1.3)
        self.layout()


def onOpenStarMap(arg):
    # type: (ServerEventReceiveAfterEvent) -> None
    global StarMapData
    StarMapData = arg.data
    if not _starMapRegistered[0]:
        clientApi.RegisterUI(StarMapNamespace, StarMapUIKey, StarMapClsPath, StarMapScreenDef)
        _starMapRegistered[0] = True
    clientApi.PushScreen(StarMapNamespace, StarMapUIKey)

client.afterEvents.serverEventReceive.subscribe("openStarMap", onOpenStarMap)
