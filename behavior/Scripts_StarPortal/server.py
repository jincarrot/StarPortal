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
    IMMERSIVE_PROPERTY = "elspirit:immersive"  # 全局"沉浸模式"开关（仅管理员可改，对所有玩家生效），默认关闭
    AREA_TELEPORT_PROPERTY = "elspirit:areaTeleport"  # 全局"范围传送"开关（仅管理员可改），默认关闭
    AREA_TELEPORT_RADIUS = 1.5  # 范围传送时一并带走的半径（方块）

    CORE_ENTITY = "elspirit:core_portal"
    SUB_ENTITY = "elspirit:sub_portal"
    TEMP_ENTITY = "elspirit:temp_portal"
    MULTI_ENTITY = "elspirit:multi_portal"  # 枢纽星塔：功能近似主星塔，但可连接多个父星塔
    PORTAL_ENTITIES = [CORE_ENTITY, SUB_ENTITY, TEMP_ENTITY, MULTI_ENTITY]
    PORTAL_LIGHT_BLOCK = "sl:portal_light"

    CORE_ITEM = "elspirit:core_portal_item"
    SUB_ITEM = "elspirit:sub_portal_item"
    MULTI_ITEM = "elspirit:multi_portal_item"
    CONTROLLER_ITEM = "elspirit:stars_controller"
    NETHER_STAR = "minecraft:nether_star"

    # 枢纽星塔本体存储在独立的动态属性中，树里只放一个指向它的标识符(marker)。
    # 标识符形如 "elspirit:ref:<portalId>"，world.getDynamicProperty(标识符) 即本体。
    REF_PREFIX = "elspirit:ref:"

    # 星塔类型 -> 实体标识符
    TYPE_ENTITY = {
        "core": CORE_ENTITY,
        "sub": SUB_ENTITY,
        "multi": MULTI_ENTITY,
    }

    CONTROLLER_COOLDOWN = 2400  # tick
    NODE_MIN_SEPARATION = 0.3   # 相邻小水晶端点之间的最小间距（方块）
    REGION_DEFAULT_SIZE = 4
    # 微缩地图中最远节点距星塔的半径（方块），由主星塔管理界面的"节点显示距离"滑动条控制
    NODE_DISPLAY_DISTANCE_MIN = 3
    NODE_DISPLAY_DISTANCE_MAX = 12
    NODE_DISPLAY_DISTANCE_DEFAULT = 5

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

    MOD_INFO = """§b§l        ✦ 星 塔 模 组 ✦§r

§7用星塔水晶搭建专属的传送网络，在网络的各个节点间自由穿梭。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 三种星塔§r
§e 主星塔§7（星核）— 网络的核心，可连向网络内所有子星塔。
§e 子星塔§7（微星石）— 网络的终点，只能传送回所属的主星塔。
§e 枢纽星塔§7— 类似主星塔，可§f同时连接多个父星塔§7把多张网络汇聚起来；也可不接父塔，独立作为根星塔。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 放置与传送§r
§7· 点击§f主星塔/枢纽星塔§7，周围浮现§f星线§7与微缩星图，点击终点虚影即可传送。
§7· 点击后屏幕下方出现§f管理按钮§7，可改名、配色、设权限，并显示传送列表。
§7· 点击§f子星塔§7可选择「传送」或「管理」。
§7· §f下蹲点击§7你放置的星塔（主／枢纽／子）都能直接打开其管理菜单。
§7· 管理中可调§f节点显示距离(5~10)§7，改变交互时浮现的微缩星图大小。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 移动星塔§r
§7§e手持星盘、下蹲点击你放置的星塔§7即可进入移动模式：星塔§f实时跟随你的视线§7移动，§e松开下蹲即固定位置§7（仅放置者可移动）。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 升级与领域§r
§7对主星塔/枢纽星塔使用§f下界之星§7可升级，附加一种§f增益效果§7。
§7站在其§f领域范围§7内的玩家会持续获得该效果（半径、音效、粒子均可调）。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 权限§r
§7每座星塔可分别设置：
§7· §f谁可以使用此星塔§7（公开／私密／指定玩家）
§7· §f谁可以传送至此星塔§7（公开／私密／指定玩家）

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 星盘（星序之盘）§r
§7· 打开§f传送菜单§7与§f星图（星座地图）§7。
§7· 移动星塔（见上）。
§7· 管理员还可用星盘：给予星塔、整体传送／管理／删除、数据修复。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 管理员开关§7（总管理菜单内）§r
§7· §f沉浸模式§7：尽量不弹表单（如点击子星塔直接传送），对所有玩家生效。
§7· §f范围传送§7：传送时把玩家周围约 1.5 格内的生物一并带走（不含星塔本身）。
§7· §f星塔可合成§7：开启后可用工作台合成星塔（配方见下）。

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§b§l ◆ 合成配方§7（需管理员开启）§r
§7 主星塔 = 紫水晶碎片×4 ＋ 钻石×4 ＋ 金粒×1
§7 子星塔 = 紫水晶碎片×4 ＋ 金粒×1
§7 星　盘 = 紫水晶碎片×4 ＋ 指南针×1

§8▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
§8由 §7ModSAPI §8提供模组支持
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
                        system.runTimeout(lambda portalId=portal.id: comp.CreateControlAi(portalId).SetBlockControlAi(False), 1)
        else:
            system.runTimeout(lambda portalId=portalId: comp.CreateControlAi(portalId).SetBlockControlAi(False), 1)

    @staticmethod
    def createTickingArea(portal):
        world.tickingAreaManager.createTickingArea(
            portal.id,
            {"dimension": portal.dimension, "from": portal.location, "to": portal.location})

    @staticmethod
    def clearPortalLight(portal):
        # type: (Entity) -> None
        """清除星塔放置的光源方块。

        注意：getBlock 在区块未加载时会返回 None，直接取 .typeId 会抛异常；
        本函数被各删除流程在 portal.remove() 之前调用，一旦抛异常就会中断删除、
        导致星塔无法删除且表单不关闭。因此这里务必保证不抛异常。
        """
        try:
            loc = portal.location
            EntityService.clearLightAt(portal.dimension.dimId, loc)
        except Exception:
            # 兜底：清除光源失败绝不能阻断删除流程
            pass

    @staticmethod
    def clearLightAt(dimId, location):
        """清除指定位置的星塔光源方块（best-effort，不抛异常）。"""
        try:
            dimension = world.getDimension(dimId)
            block = dimension.getBlock(location)
            # 能读到方块时只清除星塔自己的光源（避免误删玩家方块）；
            # 读不到（区块未加载等）时保守清除，行为与旧版一致。
            if block is None or block.typeId == Config.PORTAL_LIGHT_BLOCK:
                dimension.setBlockType(location, "minecraft:air")
        except Exception:
            pass

    @staticmethod
    def placePortalLight(dimId, location):
        """放置星塔光源方块，但只在目标处为空气或已是光源时才放置，
        避免吞掉玩家已有的方块（best-effort，不抛异常）。"""
        try:
            dimension = world.getDimension(dimId)
            block = dimension.getBlock(location)
            if block is None:
                return  # 区块未加载，无法判断，保守不放置
            if block.typeId == "minecraft:air" or block.typeId == Config.PORTAL_LIGHT_BLOCK:
                dimension.setBlockType(location, Config.PORTAL_LIGHT_BLOCK)
        except Exception:
            pass


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
            # 区块未加载时 getBlock 返回 None，按空气处理，避免取 .typeId 抛异常
            if block is not None and block.typeId != "minecraft:air":
                saveHeight = i - 1
                break
        return (location[0] + 0.5, location[1] + saveHeight, location[2] + 0.5, location[3])

    @staticmethod
    def _areaCompanions(player):
        # type: (Player) -> list
        """范围传送：玩家附近半径内、需要一并传送的实体（排除星塔自身）。"""
        if not world.getDynamicProperty(Config.AREA_TELEPORT_PROPERTY):
            return []
        loc = player.location
        try:
            nearby = player.dimension.getEntities({
                "location": {"x": loc.x, "y": loc.y, "z": loc.z},
                "maxDistance": Config.AREA_TELEPORT_RADIUS,
            })
        except Exception:
            return []
        companions = []
        for entity in nearby:
            if entity.id == player.id:
                continue
            if entity.typeId in Config.PORTAL_ENTITIES:  # 切勿把星塔一起传走
                continue
            companions.append(entity)
        return companions

    @classmethod
    def teleport(cls, player, location):
        # type: (Player, tuple) -> None
        target = cls.safeLocation(player, location)
        targetDim = world.getDimension(target[3])

        def doTeleport():
            # 在移动玩家之前，先收集其周围需要一并传送的实体
            companions = cls._areaCompanions(player)
            player.teleport(target, {"dimension": targetDim})
            player.addEffect("slow_falling", 100, {"showParticle": False})
            system.sendToClient(player, "teleportEnd", target)
            for entity in companions:
                if not entity or not entity.isValid:
                    continue
                try:
                    entity.teleport(target, {"dimension": targetDim})
                except Exception:
                    pass
        system.runTimeout(doTeleport, 40)
        system.sendToClient(player, "teleport", player.location.getTuple())


# ============================================================
# 星塔数据仓库
# ============================================================
class PortalRepository(object):
    """星塔数据仓库。

    存储态是一棵"带引用"的树：枢纽星塔(type=='multi')在父节点的 nodes 里只放
    一个标识符字符串(marker)，本体存在独立的动态属性中。load() 会把所有 marker
    解析成内存中的共享同一引用，使整棵树升级为有向无环图(DAG)，让一个枢纽同时
    挂在多个父下。save() 做逆操作：把共享的枢纽本体折叠回 marker 并写回各自属性。

    因为是 DAG（且理论上可能成环），所有递归遍历都用 visited 集合(按 id(dict))
    防止重复处理与死循环。
    """

    # ---------------- 引用解析 / 折叠 ----------------
    @staticmethod
    def _markerOf(portalData):
        return Config.REF_PREFIX + str(portalData['id'])

    def load(self):
        # type: () -> dict
        root = world.getDynamicProperty(Config.PORTAL_PROPERTY) or {}
        self._resolveNodes(root, {})
        return root

    def _resolveNodes(self, nodeDict, cache):
        """把 nodeDict 中的 marker 字符串原地替换为解析后的本体字典。
        cache: marker -> 已解析本体，保证同一 marker 全程共享同一引用，并兼作环路防护。"""
        for key in list(nodeDict.keys()):
            value = nodeDict[key]
            if isinstance(value, dict):
                self._resolveNodes(value.get("nodes", {}), cache)
                continue
            # 非字典即为 marker 字符串
            marker = value
            if marker not in cache:
                body = world.getDynamicProperty(marker)
                if not body:
                    # 引用已失效，丢弃该挂接
                    del nodeDict[key]
                    continue
                cache[marker] = body          # 先入缓存再下钻 -> 环路安全
                self._resolveNodes(body.get("nodes", {}), cache)
            nodeDict[key] = cache[marker]

    def save(self, data):
        # type: (dict) -> None
        hubBodies = {}
        serialized = self._collapse(data, hubBodies, set())
        for marker, body in hubBodies.items():
            world.setDynamicProperty(marker, body)
        world.setDynamicProperty(Config.PORTAL_PROPERTY, serialized)

    def _collapse(self, nodeDict, hubBodies, inProgress):
        """返回 nodeDict 的"序列化副本"：枢纽本体替换为 marker，并把（折叠后的）
        枢纽本体收集到 hubBodies。inProgress 防止环路时无限递归。"""
        out = {}
        for key, value in nodeDict.items():
            if not isinstance(value, dict):
                out[key] = value  # 已是 marker，原样保留
                continue
            if value.get('type') == 'multi':
                marker = self._markerOf(value)
                out[key] = marker
                if marker not in hubBodies and marker not in inProgress:
                    inProgress.add(marker)
                    body = dict(value)
                    body['nodes'] = self._collapse(value.get("nodes", {}), hubBodies, inProgress)
                    hubBodies[marker] = body
            else:
                body = dict(value)
                body['nodes'] = self._collapse(value.get("nodes", {}), hubBodies, inProgress)
                out[key] = body
        return out

    def clearHubProperty(self, portalData):
        """彻底删除枢纽时清空其本体属性，避免遗留垃圾。"""
        if portalData.get('type') == 'multi':
            world.setDynamicProperty(self._markerOf(portalData), {})

    # ---------------- 基础读写 ----------------
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
        visited = set()

        def add(portalData):
            if id(portalData) in visited:
                return
            visited.add(id(portalData))
            result.append(portalData)
            for node in portalData.get("nodes", {}).values():
                add(node)
        for portalData in data.values():
            add(portalData)
        return result

    def findById(self, portalId, data=None, visited=None):
        # type: (int, dict | None, set | None) -> dict | None
        if data is None:
            data = self.load()
        if visited is None:
            visited = set()
        for portalData in data.values():
            if id(portalData) in visited:
                continue
            visited.add(id(portalData))
            if portalData['id'] == portalId:
                return portalData
            result = self.findById(portalId, portalData.get("nodes", {}), visited)
            if result:
                return result
        return None

    def findByEntityId(self, entityId, data=None, visited=None):
        # type: (int, dict | None, set | None) -> dict | None
        if data is None:
            data = self.load()
        if visited is None:
            visited = set()
        for key, portalData in data.items():
            if key == entityId:
                return portalData
            if id(portalData) in visited:
                continue
            visited.add(id(portalData))
            result = self.findByEntityId(entityId, portalData.get("nodes", {}), visited)
            if result:
                return result
        return None

    def findParents(self, entityId, data=None, visited=None):
        # type: (int, dict | None, set | None) -> list[dict]
        """返回所有把该实体id作为子节点的父星塔（枢纽星塔可能有多个父）。"""
        if data is None:
            data = self.load()
        if visited is None:
            visited = set()
        parents = []
        for portalData in data.values():
            if id(portalData) in visited:
                continue
            visited.add(id(portalData))
            if entityId in portalData.get("nodes", {}):
                parents.append(portalData)
            parents += self.findParents(entityId, portalData.get("nodes", {}), visited)
        return parents

    def findParent(self, entityId, data=None):
        # type: (int, dict | None) -> dict | None
        """返回任一父星塔（普通星塔只有一个父；枢纽用 findParents）。"""
        parents = self.findParents(entityId, data)
        return parents[0] if parents else None

    def isAncestor(self, ancestor, node, visited=None):
        # type: (dict, dict, set | None) -> bool
        """ancestor 是否为 node 自身或其祖先（即 node 在 ancestor 的子树内）。"""
        if visited is None:
            visited = set()
        if id(ancestor) in visited:
            return False
        visited.add(id(ancestor))
        if ancestor['id'] == node['id']:
            return True
        for child in ancestor.get("nodes", {}).values():
            if self.isAncestor(child, node, visited):
                return True
        return False

    def delete(self, entityId, data=None, visited=None):
        # type: (int, dict | None, set | None) -> bool
        """从树中移除该实体id的所有挂接（枢纽可能挂在多个父下，全部移除）。"""
        if data is None:
            data = self.load()
        if visited is None:
            visited = set()
        removed = False
        if entityId in data:
            del data[entityId]
            removed = True
        for portalData in list(data.values()):
            if id(portalData) in visited:
                continue
            visited.add(id(portalData))
            if self.delete(entityId, portalData.get("nodes", {}), visited):
                removed = True
        return removed

    def linkablePortals(self, player, data=None, visited=None):
        # type: (Player, dict | None, set | None) -> list[dict]
        result = []
        if data is None:
            data = self.load()
        if visited is None:
            visited = set()
        for portalData in data.values():
            if id(portalData) in visited:
                continue
            visited.add(id(portalData))
            if Permissions.isLinkable(portalData, player):
                result.append(portalData)
            result += self.linkablePortals(player, portalData.get("nodes", {}), visited)
        return result

    def repair(self):
        # type: () -> None
        """重建缺失的星塔实体并修正数据键（DAG 安全）。"""
        data = self.load()
        remap = {}        # 旧 entityId -> 新 entityId
        processed = set()  # id(portalData)

        def process(nodeDict, parent):
            for key in list(nodeDict.keys()):
                portalData = nodeDict[key]
                if id(portalData) in processed:
                    continue
                processed.add(id(portalData))
                dimension = world.getDimension(portalData['location'][3])
                portal = world.getEntity(portalData['entityId'])
                if not portal or not portal.isValid:
                    entityType = Config.TYPE_ENTITY.get(portalData['type'], Config.CORE_ENTITY)
                    portal = dimension.spawnEntity(entityType, portalData['location'][:3:])
                    EntityService.createTickingArea(portal)
                    EntityService.disableAI(portal.id)
                portal.teleport(portalData['location'][:3:], {"dimension": dimension})
                if portalData['type'] == 'sub' and parent:
                    portal.nameTag = "%s\n前往[%s]" % (portalData['name'], parent['name'])
                else:
                    portal.nameTag = portalData['name']
                portal.setProperty("elspirit:color", portalData['color'])
                portal.setProperty("elspirit:scale", portalData['scale'])
                if portal.id != portalData['entityId']:
                    remap[portalData['entityId']] = portal.id
                    portalData['entityId'] = portal.id
                process(portalData.get("nodes", {}), portalData)
        process(data, None)

        # 实体id变化后，更新所有容器里的键（枢纽的键可能出现在多个父下）
        if remap:
            rekeyed = set()

            def rekey(nodeDict):
                if id(nodeDict) in rekeyed:
                    return
                rekeyed.add(id(nodeDict))
                for oldKey in list(nodeDict.keys()):
                    child = nodeDict[oldKey]
                    newKey = remap.get(oldKey, oldKey)
                    if newKey != oldKey:
                        del nodeDict[oldKey]
                        nodeDict[newKey] = child
                    rekey(child.get("nodes", {}))
            rekey(data)

        self.save(data)
        # 清空世界里所有未在数据中记录的星塔实体（孤儿/临时实体）
        self._removeOrphanEntities(self._collectValidEntityIds(data))

    def _collectValidEntityIds(self, data):
        # type: (dict) -> set
        """收集数据树中所有有效的星塔实体id。"""
        validIds = set()
        visited = set()

        def collect(nodeDict):
            for portalData in nodeDict.values():
                validIds.add(portalData.get('entityId'))
                if id(portalData) in visited:
                    continue
                visited.add(id(portalData))
                collect(portalData.get("nodes", {}))
        collect(data)
        return validIds

    def _removeOrphanEntities(self, validIds):
        # type: (set) -> None
        """移除世界中（已加载区块内）所有不在 validIds 中的星塔实体。
        临时星塔(temp_portal)从不记录在数据中，会被一并清理。"""
        for dimId in range(3):
            for entity in world.getDimension(dimId).getEntities():
                if entity.typeId in Config.PORTAL_ENTITIES and entity.id not in validIds:
                    EntityService.clearPortalLight(entity)
                    entity.remove()


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
# 表单：多父星塔编辑区块（枢纽星塔专用）
# ============================================================
class ParentSection(object):
    """在表单上渲染一个"多选父星塔"区块：一个下拉选择候选父星塔，一个按钮把当前
    选中项加入/移出已选集合，一段文本展示已选父星塔。result() 返回已选父星塔id列表。"""

    def __init__(self, form, candidates, initialParentIds, onChange=None):
        # candidates: list[{"label": name, "value": portalId}]
        self._candidates = candidates
        self._chosen = set(initialParentIds)
        self._onChange = onChange
        self._selection = Observable.create(0, {"clientWritable": True})
        self._info = Observable.create(self._buildInfo())
        form.label("枢纽星塔可连接多个父星塔：")
        if candidates:
            form.dropdown("选择父星塔", self._selection, candidates)
            form.button("添加/移除选中的父星塔", self._toggle)
        else:
            form.label("§7（当前没有可作为父星塔的星塔）")
        form.label(self._info)

    def _labelOf(self, portalId):
        for candidate in self._candidates:
            if candidate['value'] == portalId:
                return candidate['label']
        return str(portalId)

    def _buildInfo(self):
        info = "已选父星塔：\n"
        for portalId in self._chosen:
            info += self._labelOf(portalId) + "\n"
        if not self._chosen:
            info += "无\n"
        return info

    def _toggle(self):
        if not self._candidates:
            return
        portalId = self._selection.getData()
        if portalId in self._chosen:
            self._chosen.remove(portalId)
        else:
            self._chosen.add(portalId)
        self._info.setData(self._buildInfo())
        if self._onChange:
            self._onChange()

    def hasAny(self):
        return bool(self._chosen)

    def result(self):
        return list(self._chosen)


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
        comp.AddRecipe(self._multiRecipe())

    def setEnabled(self, enabled):
        world.setDynamicProperty(Config.DISABLE_RECIPES_PROPERTY, not enabled)
        if enabled:
            self.initial()
        else:
            comp = self._comp()
            comp.RemoveRecipe(Config.CORE_ITEM, "recipe_shaped")
            comp.RemoveRecipe(Config.SUB_ITEM, "recipe_shaped")
            comp.RemoveRecipe(Config.CONTROLLER_ITEM, "recipe_shaped")
            comp.RemoveRecipe(Config.MULTI_ITEM, "recipe_shaped")
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
    def _multiRecipe():
        return {"minecraft:recipe_shaped": {
            "description": {"identifier": Config.MULTI_ITEM},
            "tags": ["crafting_table"],
            "pattern": [" # ", "#S#", " # "],
            "key": {
                "#": {"item": "minecraft:amethyst_shard"},
                "S": {"item": Config.CORE_ITEM},
            },
            "result": [{"item": Config.MULTI_ITEM}],
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
        entries = {}     # portalId -> 下发条目（含累计的多个父id）
        visited = set()  # id(portalData)，DAG/环路防护

        def walk(nodeDict, parentId):
            for entityId, portalData in nodeDict.items():
                if not isinstance(portalData, dict):
                    continue
                pid = portalData['id']
                if Permissions.canTeleportTo(portalData, player):
                    entry = entries.get(pid)
                    if entry is None:
                        entry = {
                            "id": pid,
                            "name": portalData['name'],
                            "color": portalData.get('color', 0),
                            "type": portalData['type'],
                            "location": portalData['location'],
                            "enable": portalData.get('enable', True),
                            "parentIds": [],
                        }
                        entries[pid] = entry
                    if parentId and parentId not in entry["parentIds"]:
                        entry["parentIds"].append(parentId)
                # 子树只下钻一次（枢纽被多个父引用时避免重复/死循环）
                if id(portalData) in visited:
                    continue
                visited.add(id(portalData))
                walk(portalData.get("nodes", {}), pid)
        walk(self._repo.load(), 0)
        portals = []
        for entry in entries.values():
            entry["parentId"] = entry["parentIds"][0] if entry["parentIds"] else 0
            portals.append(entry)
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
        # 正在移动星塔的会话：playerId -> {"portalId", "lastBlock", "lastLight"}
        self._movingSessions = {}
        self._registerEvents()
        self.recipes.initial()
        system.runInterval(self.intervalFunc, 100)
        system.runInterval(self._updateMovingPortals, 1)  # 每帧让移动中的星塔跟随玩家视线

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
        # 重生/重连时取消未完成的移动星塔会话
        self._movingSessions.pop(arg.player.id, None)
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
        # 手持星盘下蹲点击自己的星塔 -> 进入移动模式（跟随视线，松开下蹲固定）
        mainHand = actor.mainHand
        if (mainHand and mainHand.typeId == Config.CONTROLLER_ITEM and actor.isSneaking
                and typeId in (Config.CORE_ENTITY, Config.SUB_ENTITY, Config.MULTI_ENTITY)):
            self._startMovePortal(actor, target)
            return
        if typeId in (Config.CORE_ENTITY, Config.MULTI_ENTITY):
            # 枢纽星塔功能与主星塔基本相同，复用同一交互逻辑
            self.onInteractCorePortal(actor, target)
        elif typeId == Config.TEMP_ENTITY:
            self.onInteractTempPortal(actor, target)
        elif typeId == Config.SUB_ENTITY:
            self.onInteractSubPortalPre(actor, target)

    def onEntityDie(self, arg):
        # type: (EntityDieAfterEvent) -> None
        if arg.deadEntity.typeId in [Config.CORE_ENTITY, Config.SUB_ENTITY, Config.MULTI_ENTITY]:
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
        refundItem = Config.MULTI_ITEM if portal.typeId == Config.MULTI_ENTITY else Config.CORE_ITEM
        portalData = self.repo.findByEntityId(portal.id)
        if not portalData:
            self._showCorruptForm(player, portal, refundItem)
            return
        portalId = portalData['id']
        if not Permissions.isUsable(portalData, player):
            player.sendMessage("§c您没有权限使用这个星塔！")
            return
        if not portalData['enable']:
            player.sendMessage("§c此星塔已被禁用！")
            return
        # 枢纽星塔可能有多个父
        parents = self.repo.findParents(portal.id)
        if not portalData['nodes'] and not parents:
            player.sendMessage("没有可连接的星塔!")
            return

        # 是否有任意可到达的目的地（子节点或任一父节点）
        canUse = False
        for node in portalData['nodes'].values():
            if Permissions.canTeleportTo(node, player):
                canUse = True
                break
        if not canUse:
            for parent in parents:
                if Permissions.canTeleportTo(parent, player):
                    canUse = True
                    break
        if not canUse:
            player.sendMessage("没有可连接的星塔!")
            return

        system.sendToClient(player, "spawnStarRegion", {
            "portalId": portalId,
            "location": portal.location.getTuple(),
            "shouldShowManager": portalData['owner'] == player.id})

        # 把每个父星塔以临时 "father_<id>" 节点的形式加入，使其也能作为传送终点显示
        fatherKeys = []
        for parent in parents:
            key = "father_%s" % parent['id']
            portalData['nodes'][key] = {
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
            fatherKeys.append(key)

        self._spawnStarNetwork(player, portal, portalData, portalId)

        for key in fatherKeys:
            portalData['nodes'].pop(key, None)

    def _spawnStarNetwork(self, player, portal, portalData, portalId):
        """生成星线与终点小水晶实体，并启动靠近检测定时器。"""
        def getMaxDistance(node, ori, visited):
            if id(node) in visited:  # DAG/环路防护
                return 0
            visited.add(id(node))
            maxLength = 0
            for subNode in node['nodes'].values():
                tar = {"x": subNode['location'][0], "y": subNode['location'][1], "z": subNode['location'][2]}
                d = {"x": tar["x"] - ori.x, "y": tar["y"] - ori.y, "z": tar["z"] - ori.z}
                length = math.sqrt(d["x"] ** 2 + d["y"] ** 2 + d["z"] ** 2)
                if length > maxLength:
                    maxLength = length
                subLength = getMaxDistance(subNode, ori, visited)
                if subLength > maxLength:
                    maxLength = subLength
            return maxLength

        maxLength = getMaxDistance(portalData, portal.location, set())
        if maxLength <= 0:
            maxLength = 1.0  # 防止除零
        # 最远节点缩放到的半径（方块），由该主星塔的"节点显示距离"决定
        displayDistance = portalData.get('nodeDisplayDistance', Config.NODE_DISPLAY_DISTANCE_DEFAULT)
        interactions = []
        expanded = set([id(portalData)])  # 已展开子节点的星塔，DAG/环路防护

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
                d = {"x": d["x"] * displayDistance / maxLength, "y": d["y"] * displayDistance / maxLength, "z": d["z"] * displayDistance / maxLength}
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
                if node['nodes'] and id(node) not in expanded:
                    expanded.add(id(node))
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

    @staticmethod
    def _isImmersive():
        # type: () -> bool
        """全局沉浸模式是否开启（尽量不弹出表单，仅管理员可在管理菜单中切换）。"""
        return bool(world.getDynamicProperty(Config.IMMERSIVE_PROPERTY))

    def _removePortalEntity(self, entityId, portal):
        # type: (int, Entity | None) -> None
        """移除星塔实体；若实体无效或所在区块未加载，则加入延后删除队列，
        待其所在区块加载后由 _deletePendingEntities 清理。整个过程不抛异常。"""
        if portal and portal.isValid:
            EntityService.clearPortalLight(portal)
            portal.remove()
        else:
            pending = world.getDynamicProperty(Config.PENDING_DELETE_PROPERTY) or []
            if entityId not in pending:
                pending.append(entityId)
            world.setDynamicProperty(Config.PENDING_DELETE_PROPERTY, pending)

    # ------------------------------------------------------------------
    # 用星盘移动星塔
    # ------------------------------------------------------------------
    def _startMovePortal(self, player, portal):
        # type: (Player, Entity) -> None
        portalData = self.repo.findByEntityId(portal.id)
        if not portalData:
            return
        if portalData['owner'] != player.id:
            player.sendMessage("§c只有星塔的放置者可以移动它！")
            return
        # 若该玩家正打开着星塔网络，先收起
        self.stopInteraction(player)
        # lastLight 预置为原位置的光源方块坐标，使第一次移动时把它清掉
        loc = portalData['location']
        self._movingSessions[player.id] = {
            "portalId": portal.id,
            "lastBlock": None,
            "lastLight": (int(loc[0]), int(loc[1]), int(loc[2]), loc[3]),
        }
        player.sendMessage("§a正在移动星塔：星塔会跟随你的视线，§e松开下蹲即可固定位置§a。")

    def _updateMovingPortals(self):
        """每帧执行：让移动中的星塔跟随各自玩家的视线方块；玩家松开下蹲则固定。"""
        if not self._movingSessions:
            return
        for playerId in list(self._movingSessions.keys()):
            session = self._movingSessions[playerId]
            playerEntity = world.getEntity(playerId)
            if not playerEntity or not playerEntity.isValid:
                self._movingSessions.pop(playerId, None)
                continue
            player = playerEntity.asPlayer()
            if not player.isSneaking:
                self._endMovePortal(player, session)
                continue
            portal = world.getEntity(session["portalId"])
            if not portal or not portal.isValid:
                self._movingSessions.pop(playerId, None)
                continue
            try:
                hit = player.getBlockFromViewDirection()
            except Exception:
                hit = None
            # 兼容返回 BlockRaycastHit(含 .block) 或直接返回方块(含 .location)
            block = None
            if hit is not None:
                inner = getattr(hit, "block", None)
                if inner is not None:
                    block = inner
                elif hasattr(hit, "location"):
                    block = hit
            if block is None:
                continue
            bpos = block.location
            blockKey = (int(bpos.x), int(bpos.y), int(bpos.z), player.dimension.dimId)
            if session["lastBlock"] == blockKey:
                continue  # 目标方块未变化，省略更新
            self._movePortalTo(portal, session, blockKey)

    def _movePortalTo(self, portal, session, blockKey):
        # type: (Entity, dict, tuple) -> None
        bx, by, bz, dimId = blockKey
        dimension = world.getDimension(dimId)
        # 星塔实体悬浮在目标方块上方一格
        newLoc = (bx + 0.5, by + 1, bz + 0.5, dimId)
        portal.teleport((newLoc[0], newLoc[1], newLoc[2]), {"dimension": dimension})
        # 光照方块：清除上一帧的，再在新位置放置（仅当新位置是空气，避免吞掉已有方块）
        lastLight = session["lastLight"]
        if lastLight:
            EntityService.clearLightAt(lastLight[3], lastLight[:3])
        EntityService.placePortalLight(dimId, (bx, by + 1, bz))
        session["lastLight"] = (bx, by + 1, bz, dimId)
        session["lastBlock"] = blockKey
        # 同步更新世界动态属性中该星塔的坐标
        data = self.repo.load()
        portalData = self.repo.findByEntityId(session["portalId"], data)
        if portalData:
            portalData['location'] = newLoc
            portalData['entityId'] = portal.id
            self.repo.save(data)

    def _endMovePortal(self, player, session):
        self._movingSessions.pop(player.id, None)
        portal = world.getEntity(session["portalId"])
        if portal and portal.isValid:
            EntityService.createTickingArea(portal)  # 在新位置重建常加载区域
        player.sendMessage("§a星塔位置已固定。")

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

        # 下蹲点击：放置者直接打开子星塔管理界面（非放置者则走正常流程）
        if player.isSneaking and portalData['owner'] == player.id:
            self._showSubPortalManager(player, portal, portalData, data)
            return

        # 沉浸模式：可传送的子星塔直接传送，不弹出操作表单
        if self._isImmersive() and portalData['enable']:
            self.onInteractSubPortal(player, portal)
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
                alert.close()
                entityId = portalData['entityId']
                self.repo.delete(entityId, data)
                self.repo.save(data)
                self.stopInteraction(player)
                self._removePortalEntity(entityId, portal)
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
            self._showCreatePortalForm(arg, player, "core")
        elif itemType == Config.SUB_ITEM:
            self._showCreatePortalForm(arg, player, "sub")
        elif itemType == Config.MULTI_ITEM:
            self._showCreatePortalForm(arg, player, "multi")
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

    def _showCreatePortalForm(self, arg, player, kind):
        # kind: "core" | "sub" | "multi"
        isCore, isSub, isMulti = kind == "core", kind == "sub", kind == "multi"
        portalName = Observable.create("", {"clientWritable": True})
        portalColor = Observable.create(0, {"clientWritable": True})
        if kind == "multi":
            portalColor.setData(4)
        scale = Observable.create(1 if isSub else 4, {"clientWritable": True})
        parentNode = Observable.create(0, {"clientWritable": True})  # 单父（core/sub）
        anchorToggle = Observable.create(False, {"clientWritable": True})

        candidates = [{"label": node['name'], "value": node['id']} for node in self.repo.linkablePortals(player)]
        nodes = [{"label": "无", "value": 0}] + candidates

        # 创建按钮始终显示；条件不满足时按钮上显示原因，点击不处理
        def validate():
            if not portalName.getData():
                return "§c请输入星塔名称"
            if isSub and not parentNode.getData():
                return "§c请选择父星塔"
            # 枢纽星塔不强制要求父节点，可像主星塔一样作为根节点
            return None

        submitLabel = Observable.create("§c请输入星塔名称")

        def refreshButton(*args):
            error = validate()
            submitLabel.setData(error if error else "创建星塔")
        portalName.subscribe(refreshButton)
        if isSub:
            parentNode.subscribe(refreshButton)

        entityType = Config.TYPE_ENTITY[kind]

        def onSubmit():
            if validate() is not None:
                return  # 条件不满足，点击不处理
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
            body = {
                "entityId": portal.id,
                "id": portalId,
                "name": portalName.getData(),
                "color": portalColor.getData(),
                "scale": scale.getData(),
                "location": (loc.x, loc.y, loc.z, player.dimension.dimId),
                "owner": player.id,
                "usePermissions": useSection.result(),
                "teleportPermissions": teleportSection.result(),
                "type": kind,
                "enable": True,
                "nodes": {},
            }
            if isMulti:
                parentIds = parentSection.result()
                if parentIds:
                    # 同一本体对象挂到每个选中的父下，save() 会折叠成 marker
                    for parentId in parentIds:
                        parent = self.repo.findById(parentId, data)
                        if parent:
                            parent.setdefault("nodes", {})
                            parent['nodes'][portal.id] = body
                else:
                    data[portal.id] = body  # 未选父星塔 -> 作为根节点
                portal.nameTag = portalName.getData()
            else:
                parent = self.repo.findById(parentNode.getData(), data)
                container = parent if parent else {"nodes": data}
                container.setdefault("nodes", {})
                container['nodes'][portal.id] = body
                if isSub:
                    portal.nameTag = "%s\n前往[%s]" % (portalName.getData(), parent['name'] if parent else "?")
                else:
                    portal.nameTag = portalName.getData()
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
        elif isSub:
            form = CustomForm.create(player, "创建子星塔")
            form.label("""§b§l子星塔§r是一个星塔网络的§b§l终点水晶§r，\n
您需要先放置§b§l主晶塔（使用星核）§r并设置子晶塔所属的主星塔以使用传送。\n
子星塔只能传送到§b§l其所属的主星塔§r。""")
            form.divider()
            form.dropdown("主星塔", parentNode, nodes)
            form.textField("星塔名称", portalName)
            form.dropdown("星塔颜色", portalColor, Config.COLORS)
            form.slider("星塔尺寸", scale, 1, 16)
        else:  # multi
            form = CustomForm.create(player, "创建枢纽星塔")
            form.label("""§b§l枢纽星塔§r功能与§b§l主星塔§r基本相同，但§b§l可以同时连接多个父星塔§r，\n
用于把多个星塔网络汇聚到一起。\n
可选择任意数量的父星塔；不选则与主星塔一样作为根节点。""")
            form.divider()
            form.textField("星塔名称", portalName)
            form.dropdown("星塔颜色", portalColor, Config.COLORS)
            form.slider("星塔尺寸", scale, 1, 16)
            form.divider()
            parentSection = ParentSection(form, candidates, [], onChange=refreshButton)

        form.divider()
        useSection = PermissionSection(form, "谁可以使用此星塔", "可使用的玩家：", "private")
        form.divider()
        teleportSection = PermissionSection(form, "谁可以传送至此星塔", "可传送至此的玩家：", "private")
        if StarTeam.available():
            form.divider()
            form.toggle("是否设置为工会锚点", anchorToggle)
        form.divider()
        form.button(submitLabel, onSubmit)
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
            itemTypes = [{"label": "主星塔", "value": 0}, {"label": "子星塔", "value": 1}, {"label": "枢纽星塔", "value": 2}]
            giveItems = [Config.CORE_ITEM, Config.SUB_ITEM, Config.MULTI_ITEM]
            giveNames = ["主星塔", "子星塔", "枢纽星塔"]
            itemSelection = Observable.create(0, {"clientWritable": True})
            amount = Observable.create(1, {"clientWritable": True})

            def onSubmit():
                giveForm.close()
                target = world.getEntity(playerList[playerSelection.getData()]['extra']).asPlayer()
                itemId = giveItems[itemSelection.getData()]
                target.container.addItem(ItemStack(itemId, amount.getData()))
                target.sendMessage("已收到管理员[%s]赠与的%s个%s！" % (
                    admin.name, amount.getData(), giveNames[itemSelection.getData()]))
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
                visited = set()

                def removeTree(nodeDict):
                    for entityId in list(nodeDict.keys()):
                        child = nodeDict[entityId]
                        if id(child) in visited:  # DAG/环路防护
                            continue
                        visited.add(id(child))
                        admin.sendMessage("星塔[%s]已删除" % child['name'])
                        portal = world.getEntity(entityId)
                        if portal and portal.isValid:
                            EntityService.clearPortalLight(portal)
                            portal.remove()
                        else:
                            portalsNeedDel.append(entityId)
                        if child.get('type') == 'multi':
                            self.repo.clearHubProperty(child)
                        removeTree(child.get('nodes', {}))
                removeTree({portalData['entityId']: portalData})
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
            info = Observable.create("§7修复会：重建数据中记录但丢失的星塔实体，并清除世界中所有未被数据记录的星塔（含残留的临时星塔）。\n ")

            def doRepair():
                visibility.setData(False)
                self.repo.repair()
                info.setData("数据修复完成！")

            def clearData():
                visibility.setData(False)
                info.setData("数据清空完成！")
                self.repo.save({})
                for entityType in Config.PORTAL_ENTITIES:
                    admin.dimension.runCommand("kill @e[type=%s]" % entityType)
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

        immersive = Observable.create(self._isImmersive(), {"clientWritable": True})

        def onImmersiveChange(value):
            world.setDynamicProperty(Config.IMMERSIVE_PROPERTY, value)
        immersive.subscribe(onImmersiveChange)

        areaTeleport = Observable.create(bool(world.getDynamicProperty(Config.AREA_TELEPORT_PROPERTY)), {"clientWritable": True})

        def onAreaTeleportChange(value):
            world.setDynamicProperty(Config.AREA_TELEPORT_PROPERTY, value)
        areaTeleport.subscribe(onAreaTeleportChange)

        form = CustomForm.create(admin, "星塔管理菜单")
        form.spacer()
        # form.button("§b星图（星座地图）", openMap)
        form.button("模组介绍", intro)
        form.button("给予玩家星塔", give)
        form.button("传送至星塔", teleport)
        form.button("删除星塔", delete)
        form.button("数据修复", repair)
        form.toggle("沉浸模式", immersive)
        form.toggle("开启范围传送", areaTeleport)
        form.toggle("星塔可合成", enableRecipes)
        form.show()

    # ------------------------------------------------------------------
    # 星塔控制器（普通玩家）
    # ------------------------------------------------------------------
    def _showPlayerController(self, arg, player):
        # type: (ItemStartUseOnAfterEvent, Player) -> None
        form = CustomForm.create(player, "传送")
        # form.button("§b星图（星座地图）", lambda: (form.close(), self.starMap.openFor(player)))
        form.label("请选择要传送的星塔\n ")

        def directTeleport(portalData):
            if not StarMapService.checkCooldown(player):
                form.close()
                return
            player.teleport(portalData['location'], {"dimension": world.getDimension(portalData['location'][3])})
            player.setDynamicProperty(Config.LAST_CONTROLLER_USE_PROPERTY, world.getAbsoluteTime())
            controller = player.mainHand
            durability = controller.getComponent("minecraft:durability") # type: (ItemDurabilityComponent)
            durability.damage += 1
            if durability.remain == 0:
                player.mainHand = None
            else:
                player.mainHand = controller
            form.close()
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
        nodeDistance = Observable.create(portalData.get('nodeDisplayDistance', Config.NODE_DISPLAY_DISTANCE_DEFAULT), {"clientWritable": True})
        isMulti = portalData['type'] == 'multi'
        # 候选父星塔：可连接、且不是自身或自身的后代（防止成环）
        candidates = []  # type: list[DropdownItem]
        for node in self.repo.linkablePortals(player):
            if not self.repo.isAncestor(portalData, node):
                candidates.append({"label": node['name'], "value": node['id']})
        parentNode = None
        if isMulti:
            currentParentIds = [p['id'] for p in self.repo.findParents(portal.id)]
        else:
            linkableNodes = [{"label": "无", "value": 0}] + candidates
            parentData = self.repo.findParent(portal.id)
            parentNode = Observable.create(parentData['id'] if parentData else 0, {"clientWritable": True})
        isEnabled = Observable.create(portalData['enable'], {"clientWritable": True})

        managerTitle = "枢纽星塔管理" if isMulti else "星塔管理"
        manager = CustomForm.create(player, managerTitle, {"closable": False, "movable": True, "resizable": True})
        manager.textField("星塔名称", portalName)
        manager.slider("星塔尺寸", portalScale, 1, 16)
        manager.dropdown("星塔颜色", portalColor, Config.COLORS)
        manager.slider("节点显示距离", nodeDistance, Config.NODE_DISPLAY_DISTANCE_MIN, Config.NODE_DISPLAY_DISTANCE_MAX)
        manager.divider()
        useSection = PermissionSection(manager, "谁可以使用此星塔", "可使用的玩家：", Permissions.use(portalData))
        manager.divider()
        teleportSection = PermissionSection(manager, "谁可以传送至此星塔", "可传送至此的玩家：", Permissions.teleport(portalData))
        manager.divider()
        if isMulti:
            parentSection = ParentSection(manager, candidates, currentParentIds)
        else:
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
            portalData['nodeDisplayDistance'] = nodeDistance.getData()
            portalData['usePermissions'] = useSection.result()
            portalData['teleportPermissions'] = teleportSection.result()
            portalData.pop('permissions', None)
            self.repo.delete(portal.id, data)  # 先摘掉所有旧挂接，再按新选择重挂
            if isMulti:
                parentIds = parentSection.result()
                if parentIds:
                    for parentId in parentIds:
                        parent = self.repo.findById(parentId, data)
                        if parent:
                            parent.setdefault("nodes", {})
                            parent['nodes'][portal.id] = portalData
                else:
                    data[portal.id] = portalData  # 未选父星塔 -> 作为根节点
            elif parentNode.getData() == 0:
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
                # 先关闭表单并落库（关键的持久化），再处理实体，保证即使实体操作异常也不影响删除生效
                alert.close()
                entityId = portalData['entityId']
                self.repo.delete(entityId, data)
                if isMulti:
                    self.repo.clearHubProperty(portalData)
                self.repo.save(data)
                self.stopInteraction(player)
                self._removePortalEntity(entityId, portal)
                player.container.addItem(ItemStack(Config.MULTI_ITEM if isMulti else Config.CORE_ITEM, 1))
            alert = CustomForm.create(player, "删除星塔")
            hint = "§c枢纽星塔会从所有父星塔处一并删除。§r\n" if isMulti else ""
            alert.label("§c您确定要删除这个星塔吗？§r\n%s删除后将无法使用这个星塔进行传送\n" % hint)
            alert.button("取消", alert.close)
            alert.button("删除", action)
            alert.show()

        manager.button("提交", submit)
        manager.button("§4删除此星塔", delete)

        # 传送列表
        def onTeleport(targetEntity):
            ui.close()
            # 沉浸模式：跳过传送确认，直接传送
            if self._isImmersive():
                self.onInteractTempPortal(player, targetEntity)
                return

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

    def _applyEffects(self, data=None, visited=None):
        if data is None:
            data = self.repo.load()
        if visited is None:
            visited = set()
        for portalId in data:
            portalData = data[portalId]
            if id(portalData) in visited:  # 枢纽被多个父引用，只处理一次
                continue
            visited.add(id(portalData))
            location = portalData['location']
            EntityService.placePortalLight(location[3], location[:3])
            # 枢纽星塔与主星塔一样可承载领域增益
            if portalData['type'] in ('core', 'multi') and portalData['enable']:
                self._applyCoreEffects(portalData)
            self._applyEffects(portalData.get("nodes", {}), visited)

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
    def initialNodes(self, nodes=None, visited=None):
        if nodes is None:
            nodes = self.repo.load()
        if visited is None:
            visited = set()
        for portalId in nodes:
            portalData = nodes[portalId]
            if id(portalData) in visited:  # DAG/环路防护
                continue
            visited.add(id(portalData))
            location = portalData['location']
            dimension = world.getDimension(location[3])
            world.tickingAreaManager.createTickingArea(
                portalId, {"dimension": dimension, "from": location, "to": location})
            self.initialNodes(portalData.get("nodes", {}), visited)

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
