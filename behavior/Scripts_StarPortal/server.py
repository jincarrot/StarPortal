# -*- coding: utf-8 -*-
import math
import json
import random

from ModSAPI.server.beta import *
from ModSAPI.serverui.beta import *


# sys.stdout = stream

"""
Data structure:

world.portals: {
    entityId: {
        entityId: entityId,
        id: int,
        name: string,
        color: int,
        scale: int,
        location: tuple[x, y, z, dimId],
        owner: playerId,
        permissions: "public" | "private" | playerId[],
        type: "core" | "sub",
        effects: {
            effectType: {
                level: int,
                enable: bool
            }
        },
        regionSize: int,
        enable: bool,
        nodes: { ... }
    }
}
world.portalId: int
"""
colors = [
    {
        "label": "蓝",
        "value": 0
    },
    {
        "label": "绿",
        "value": 2
    },
    {
        "label": "红",
        "value": 1
    },
    {
        "label": "黄",
        "value": 3
    },
    {
        "label": "浅紫",
        "value": 4
    },
    {
        "label": "浅蓝",
        "value": 5
    },
    {
        "label": "黑",
        "value": 6
    }
] # type: list[DropdownItem]
positiveEffects = {
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
    "saturation": "饱和"
}
modInfo = """
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

def getStarTeam():
    import mod.server.extraServerApi as serverApi
    teamSys = serverApi.GetSystem("ModSAPIForStarTeam", "system")
    if teamSys:
        teamSys = teamSys.importFunc("teamSys")
        return teamSys

def addStarTeamAnchor(player, identifier, location):
    team = getStarTeam().getTeam(player)
    team.addTeleportAnchor(identifier, location, "portal")

def removeStarTeamAnchor(player, identifier):
    team = getStarTeam().getTeam(player)
    team.removeTeleportAnchor(identifier)

def getPortalData():
    # type: () -> dict
    """Get portal data."""
    return world.getDynamicProperty("elspirit:portals") or {}

def getPortalDataList():
    # type: () -> list[dict]
    """Get portal data in list form."""
    data = getPortalData()
    result = []
    def addToList(portalData):
        result.append(portalData)
        for node in portalData.get("nodes", {}).values():
            addToList(node)
    for portal in data.values():
        addToList(portal)
    return result

def getIsLinkable(portalData, player):
    # type: (dict, Player) -> bool
    """Get whether the portal is linkable for the player."""
    if portalData['type'] == 'sub':
        return False
    if portalData['owner'] == player.id:
        return True
    if portalData['permissions'] == 'public':
        return True
    elif portalData['permissions'] == "private" and portalData['owner'] == player.id:
        return True
    elif player.name in portalData['permissions']:
        return True
    return False

def getIsUsable(portalData, player):
    # type: (dict, Player) -> bool
    """Get whether the portal is usable for the player."""
    if portalData['owner'] == player.id:
        return True
    if portalData['permissions'] == 'public':
        return True
    elif portalData['permissions'] == "private" and portalData['owner'] == player.id:
        return True
    elif player.name in portalData['permissions']:
        return True
    return False

def getPortalDataById(portalId, data=None):
    # type: (int, dict | None) -> dict | None
    """Get portal data by ID."""
    if data is None:
        data = getPortalData()
    for portal in data.values():
        if portal['id'] == portalId:
            return portal
        result = getPortalDataById(portalId, portal.get("nodes", {}))
        if result:
            return result
    return None

def getPortalDataByEntityId(entityId, data=None):
    # type: (int, dict | None) -> dict | None
    """Get portal data by entity ID."""
    if data is None:
        data = getPortalData()
    for portal in data:
        if portal == entityId:
            return data[portal]
        result = getPortalDataByEntityId(entityId, data[portal].get("nodes", {}))
        if result:
            return result

def getAllLinkablePortals(player, data=None):
    # type: (Player, dict | None) -> list[dict]
    """Get all linkable portals for the player."""
    portals = []
    if data is None:
        data = getPortalData()
    for portal in data.values():
        if getIsLinkable(portal, player):
            portals.append(portal)
        portals += getAllLinkablePortals(player, portal.get("nodes", {}))
    return portals

def getParentByEntityId(entityId):
    nodes = getPortalData()
    while nodes:
        for portalId in nodes:
            if entityId in nodes[portalId].get("nodes", {}):
                return nodes[portalId]
        nodes = nodes[portalId].get("nodes", {})

def getIsParent(portalDataA, portalDataB):
    """Returns true if portalDataA is a parent of portalDataB."""
    if portalDataA['id'] == portalDataB['id']:
        return True
    for node in portalDataA.get("nodes", {}).values():
        if getIsParent(node, portalDataB):
            return True
    return False

def deletePortalData(entityId, data=None):
    if data is None:
        data = getPortalData()
    for portalId in list(data.keys()):
        if portalId == entityId:
            del data[portalId]
            return True
        if deletePortalData(entityId, data[portalId].get("nodes", {})):
            return True
    return False

def repairPortalData(data=None):
    if data is None:
        data = getPortalData()
    for entityId in list(data.keys()):
        portal = world.getEntity(entityId)
        if not portal or not portal.isValid:
            portal = world.getDimension(data[entityId]['location'][3]).spawnEntity("elspirit:%s_portal" % data[entityId]['type'], data[entityId]['location'][:3:])
        portal.teleport(data[entityId]['location'][:3:], {"dimension": world.getDimension(data[entityId]['location'][3])})
        name = data[entityId]['name']
        color = data[entityId]['color']
        scale = data[entityId]['scale']
        portal.nameTag = name
        portal.setProperty("elspirit:color", color)
        portal.setProperty("elspirit:scale", scale)
        repairPortalData(data[entityId].get("nodes", {}))
        if portal.id != entityId:
            temp = data[entityId]
            temp['entityId'] = portal.id
            del data[entityId]
            data[portal.id] = temp
            world.setDynamicProperty("elspirit:portals", data)

@world.afterEvents.playerSpawn.subscribe
def onPlayerSpawn(arg):
    # type: (PlayerSpawnAfterEvent) -> None
    stopInteraction(arg.player)

@world.beforeEvents.entityHurt.subscribe
def onEntityHurtBefore(arg):
    # type: (EntityHurtBeforeEvent) -> None
    attacker = arg.damageSource.damagingEntity
    if not attacker or attacker.typeId != "minecraft:player":
        return
    if arg.hurtEntity.typeId == "elspirit:core_portal":
        onInteractCorePortal(attacker, arg.hurtEntity)
    elif arg.hurtEntity.typeId == "elspirit:temp_portal":
        onInteractTempPortal(attacker, arg.hurtEntity)
    elif arg.hurtEntity.typeId == "elspirit:sub_portal":
        onInteractSubPortalPre(attacker, arg.hurtEntity)

@world.afterEvents.playerInteractWithEntity.subscribe
def onInteract(arg):
    # type: (PlayerInteractWithEntityAfterEvent) -> None
    if arg.target.typeId == "elspirit:core_portal":
        onInteractCorePortal(arg.player, arg.target)
    elif arg.target.typeId == "elspirit:temp_portal":
        onInteractTempPortal(arg.player, arg.target)
    elif arg.target.typeId == "elspirit:sub_portal":
        onInteractSubPortalPre(arg.player, arg.target)

def onInteractCorePortal(player, portal):
    # type: (Player, Entity) -> None
    if player.isSneaking and (not player.mainHand or (player.mainHand and player.mainHand.typeId != "minecraft:nether_star")):
        portalData = getPortalDataByEntityId(portal.id)
        if not getIsUsable(portalData, player):
            player.sendMessage("§c您没有权限使用这个星塔！")
            return
        class temp:
            def __init__(self, data):
                self.data = data
        system.run(lambda: openStarPortalManager(temp({"playerId": player.id, "portalId": portalData['id']})))
        if player.getDynamicProperty("elspirit:interactions"):
            return
    if player.mainHand and player.mainHand.typeId == "minecraft:nether_star":
        data = getPortalData()
        portalData = getPortalDataByEntityId(portal.id, data)
        if portalData['owner'] != player.id:
            player.sendMessage("§c您没有权限升级这个星塔！")
            return
        addedEffects = portalData.get("effects", {})
        effects = [] # type: list[DropdownItem]
        index = 0
        for effect in positiveEffects:
            if effect not in addedEffects:
                effects.append({
                    "label": positiveEffects[effect],
                    "value": index,
                    "extra": effect
                })
                index += 1
        effectSelection = Observable.create(0, {"clientWritable": True})
        levelSelection = Observable.create(1, {"clientWritable": True})
        def submit():
            effectType = effects[effectSelection.getData()]["extra"]
            level = levelSelection.getData() - 1
            addedEffects[effectType] = {
                "level": level,
                "enable": True
            }
            portalData['effects'] = addedEffects
            world.setDynamicProperty("elspirit:portals", data)
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
        return
    if player.getDynamicProperty("elspirit:interactions"):
        stopInteraction(player, None)
        return
    portal.setDynamicProperty("elspirit:is_using", True)
    portalData = getPortalDataByEntityId(portal.id)
    portalId = portalData['id']
    if not portalData:
        def delete():
            form.close()
            clearPortalLight(portal)
            portal.remove()
            player.container.addItem(ItemStack("elspirit:core_portal_item", 1))
        form = CustomForm.create(player, "错误")
        form.label("数据发生错误，可能是父节点被移除。")
        form.label("是否删除该晶塔？")
        form.button("删除", delete)
        form.button("取消", form.close)
        form.show()
        return
    if not getIsUsable(portalData, player):
        player.sendMessage("§c您没有权限使用这个星塔！")
        return
    if not portalData['enable']:
        player.sendMessage("§c此星塔已被禁用！")
        return
    canUse = False
    if not portalData['nodes'] and not getParentByEntityId(portal.id):
        player.sendMessage("没有可连接的星塔!")
        return
    for node in portalData['nodes'].values():
        if getIsUsable(node, player):
            canUse = True
            break
    parent = getParentByEntityId(portal.id)
    if parent and getIsUsable(parent, player):
        canUse = True
    if not canUse:
        player.sendMessage("没有可连接的星塔!")
        return
    system.sendToClient(player, "spawnStarRegion", {"portalId": portalId, "location": portal.location.getTuple(), "shouldShowManager": portalData['owner'] == player.id})
    parent = getParentByEntityId(portal.id)
    if parent:
        portalData['nodes']["father"] = {
            "id": parent['id'],
            "name": parent['name'],
            "color": parent['color'],
            "scale": parent['scale'],
            "location": parent['location'],
            "owner": parent['owner'],
            "permissions": parent['permissions'],
            "type": parent['type'],
            "nodes": {}
        }
    def getMaxDistance(node, ori):
        maxLength = 0
        for subNode in node['nodes'].values():
            tar = {"x": subNode['location'][0], "y": subNode['location'][1], "z": subNode['location'][2]}
            dir = { "x": tar["x"] - ori.x, "y": tar["y"] - ori.y, "z": tar["z"] - ori.z }
            length = math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2)
            if length > maxLength:
                maxLength = length
            subLength = getMaxDistance(subNode, ori)
            if subLength > maxLength:
                maxLength = subLength
        return maxLength
    maxLength = getMaxDistance(portalData, portal.location)
    interactions = []
    def spawnNodes(ori, portalData):
        ori = {"x": ori.x, "y": ori.y, "z": ori.z}
        
        for node in portalData['nodes'].values():
            if not getIsUsable(node, player):
                continue
            tar = {"x": node['location'][0], "y": node['location'][1] + 0.3 + portalData['scale'] * 0.2, "z": node['location'][2]}
            ori2 = {"x": ori['x'], "y": (ori['y'] + 0.3 + portalData['scale'] * 0.2) if portalData['id'] == portalId else (ori['y'] + 0.15), "z": ori['z']}
            dir = { "x": tar["x"] - ori2['x'], "y": tar["y"] - ori2['y'], "z": tar["z"] - ori2['z'] }
            length = math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2)
            dir = { "x": dir["x"] * 4.0 / maxLength, "y": dir["y"] * 4.0 / maxLength, "z": dir["z"] * 4.0 / maxLength}
            if math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2) < portalData['scale'] * 0.2:
                dir = {
                    "x": dir["x"] * portalData['scale'] * 0.2 / math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2),
                    "y": dir["y"] * portalData['scale'] * 0.2 / math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2),
                    "z": dir["z"] * portalData['scale'] * 0.2 / math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2)
                }
            entity = portal.dimension.spawnEntity(
                "elspirit:temp_portal", 
                (ori2['x'] + dir["x"], ori2['y'] + dir["y"] - 0.15, ori2['z'] + dir["z"]))
            entity.setDynamicProperty("elspirit:portalId", node['id'])
            entity.setDynamicProperty("elspirit:mainPortalEntityId", portal.id)
            entity.nameTag = "%s\n%s" % (node['name'], node['location'][:3:])
            entity.setProperty("elspirit:color", node['color'])
            interactions.append(entity.id)
            length = math.sqrt(dir["x"] ** 2 + dir["y"] ** 2 + dir["z"] ** 2)
            system.sendToClient(player, "spawnStarLine", {
                "molang": {
                    "size_x": length / 2.0,
                    "direction_x": dir["x"],
                    "direction_y": dir["y"],
                    "direction_z": dir["z"]
                },
                "location": (ori["x"] + dir["x"] / 2, ori2["y"] + dir["y"] / 2, ori2["z"] + dir["z"] / 2)
            })
            players = world.getAllPlayers()
            players.remove(player)
            system.sendToClient(players, "hideNode", entity.id)
            if node['nodes']:
                spawnNodes(entity.location, node)
    spawnNodes(portal.location, portalData)
    if portalData['nodes'].get("father"):
        del portalData['nodes']["father"]
    def onInterval():
        if not portal or not portal.isValid:
            system.clearRun(timer)
            return
        players = world.getAllPlayers()
        shouldStop = True
        for p in players:
            vec = portal.location - p.location
            if math.sqrt(vec.x ** 2 + vec.y ** 2 + vec.z ** 2) < 15:
                shouldStop = False
                break
        if shouldStop:
            stopInteraction(player, portal)
            system.clearRun(timer)
    timer = system.runInterval(onInterval, 10)
    player.setDynamicProperty("elspirit:interactions", interactions)

def stopInteraction(player, portal=None):
    # type: (Player, Entity | None) -> None
    if portal:
        portal.setDynamicProperty("elspirit:is_using", False)
    interactions = player.getDynamicProperty("elspirit:interactions")
    if interactions:
        system.sendToClient(player, "stopInteraction", None)
        for entityId in interactions:
            entity = world.getEntity(entityId)
            if entity:
                entity.remove()
    player.setDynamicProperty("elspirit:interactions", [])

def onInteractTempPortal(player, portal):
    # type: (Player, Entity) -> None
    portalData = getPortalDataById(portal.getDynamicProperty("elspirit:portalId"))
    if not getIsUsable(portalData, player):
        player.sendMessage("§c您没有权限使用这个星塔！")
        return
    stopInteraction(player, world.getEntity(portal.getDynamicProperty("elspirit:mainPortalEntityId")))
    if not portalData:
        print("Error in temp portal interaction!")
        return
    if not portalData['enable']:
        player.sendMessage("§c此星塔已被禁用！")
        return
    targetLocation = portalData['location']
    saveHeight = 4
    for i in range(1, 4):
        if player.dimension.getBlock((targetLocation[0], targetLocation[1] + i, targetLocation[2])).typeId != "minecraft:air":
            saveHeight = i - 1
            break
    targetLocation = (targetLocation[0] + 0.5, targetLocation[1] + saveHeight, targetLocation[2] + 0.5, targetLocation[3])
    def doTeleport():
        player.teleport(targetLocation, {"dimension": world.getDimension(targetLocation[3])})
        player.addEffect("slow_falling", 100, {"showParticle": False})
        system.sendToClient(player, "teleportEnd", targetLocation)
    system.runTimeout(doTeleport, 40)
    system.sendToClient(player, "teleport", player.location.getTuple())

def onInteractSubPortalPre(player, portal):
    # type: (Player, Entity) -> None
    data = getPortalData()
    portalData = getPortalDataByEntityId(portal.id, data)
    if not portalData:
        def delete():
            form.close()
            clearPortalLight(portal)
            portal.remove()
            player.container.addItem(ItemStack("elspirit:sub_portal_item", 1))
        form = CustomForm.create(player, "错误")
        form.label("数据发生错误，可能是父节点被移除。")
        form.label("是否删除该晶塔？")
        form.button("删除", delete)
        form.button("取消", form.close)
        form.show()
        return
    if not getIsUsable(portalData, player):
        player.sendMessage("§c您没有权限使用这个星塔！")
        return
    def teleport():
        onInteractSubPortal(player, portal)
        actions.close()
    def manage():
        if portalData['owner'] != player.id:
            player.sendMessage("§c您没有权限管理这个星塔！")
            return
        actions.close()
        # Manager
        # Observables
        players = portalData['permissions']
        if not isinstance(players, list):
            players = []
        permission = Observable.create(1 if portalData['permissions'] == 'public' else 0 if portalData['permissions'] == 'private' else 2, {"clientWritable": True})
        playerName = Observable.create("", {"clientWritable": True})
        playerNameInputVisibility = Observable.create(permission.getData() == 2, {"clientWritable": True})
        info = "可使用的玩家：\n"
        for pName in players:
            info += pName + "\n"
        if not players:
            info += "无\n"
        portalName = Observable.create(portalData['name'], {"clientWritable": True})
        portalScale = Observable.create(portalData['scale'], {"clientWritable": True})
        portalColor = Observable.create(portalData['color'], {"clientWritable": True})
        currentPlayersInfo = Observable.create(info)
        btnName = Observable.create("添加玩家")
        linkableNodes = []# type: list[DropdownItem]
        for node in getAllLinkablePortals(player):
            if not getIsParent(portalData, node):
                linkableNodes.append({
                    "label": node['name'],
                    "value": node['id']
                })
        parentData = getParentByEntityId(portal.id)
        parentNode = Observable.create(parentData['id'] if parentData else 0, {"clientWritable": True})
        isEnabled = Observable.create(portalData['enable'], {"clientWritable": True})
        @permission.subscribe
        def onPermissionChange(new_value):
            playerNameInputVisibility.setData(new_value == 2)
        @playerName.subscribe
        def onPlayerNameChange(new_value):
            btnName.setData("添加玩家" if new_value not in players else "§4移除玩家")
        def addOrRemovePlayer():
            if not playerName.getData():
                return
            if playerName.getData() in players:
                players.remove(playerName.getData())
            else:
                players.append(playerName.getData())
            info = "可使用的玩家：\n"
            for pName in players:
                info += pName + "\n"
            if not players:
                info += "无\n"
            currentPlayersInfo.setData(info)
            playerName.setData("")

        def submit():
            parent = getParentByEntityId(portal.id)
            portal.nameTag = "%s\n前往[%s]" % (portalName.getData(), parent['name'])
            portal.setProperty("elspirit:color", portalColor.getData())
            portal.setProperty("elspirit:scale", portalScale.getData())
            portalData['name'] = portalName.getData()
            portalData['color'] = portalColor.getData()
            portalData['scale'] = portalScale.getData()
            if permission.getData() == 2:
                portalData['permissions'] = players
            else:
                portalData['permissions'] = ['private', "public"][permission.getData()]
            deletePortalData(portal.id, data)
            if parentNode.getData() == 0:
                targetNode = data
            else:
                targetNode = getPortalDataById(parentNode.getData(), data)
            targetNode['nodes'][portal.id] = portalData
            world.setDynamicProperty("elspirit:portals", data)
            manager.close()

        def delete():
            manager.close()
            def action():
                stopInteraction(player, portal)
                clearPortalLight(portal)
                portal.remove()
                deletePortalData(portal.id, data)
                world.setDynamicProperty("elspirit:portals", data)
                alert.close()
                player.container.addItem(ItemStack("elspirit:sub_portal_item", 1))
            alert = CustomForm.create(player, "删除星塔")
            alert.label("§c您确定要删除这个星塔吗？§r\n删除后将无法使用这个星塔进行传送\n")
            alert.button("取消", alert.close)
            alert.button("删除", action)
            alert.show()

        @isEnabled.subscribe
        def switchEnableState(value):
            portalData['enable'] = value
        # Form
        manager = CustomForm.create(player, "星塔管理")
        manager.textField("星塔名称", portalName)
        manager.slider("星塔尺寸", portalScale, 1, 16)
        manager.dropdown("星塔颜色", portalColor, colors)
        manager.divider()
        manager.dropdown("权限设置", permission, [
            {
                "label": "公开",
                "value": 1
            },
            {
                "label": "私密",
                "value": 0
            },
            {
                "label": "指定玩家",
                "value": 2
            }
        ])
        manager.label(currentPlayersInfo, {"visible": playerNameInputVisibility})
        manager.textField("玩家名称", playerName, {"visible": playerNameInputVisibility})
        manager.button(btnName, addOrRemovePlayer, {"visible": playerNameInputVisibility})
        manager.divider()
        manager.dropdown("主星塔", parentNode, linkableNodes)
        manager.divider()
        manager.toggle("是否启用", isEnabled)
        manager.divider()

        manager.button("提交", submit)
        manager.button("§4删除此星塔", delete)
        manager.show()

    actions = CustomForm.create(player, "子星塔")
    actions.button("传送", teleport, {"visible": portalData['enable']})
    actions.button("管理", manage)
    actions.show()
    
def onInteractSubPortal(player, portal):
    # type: (Player, Entity) -> None
    portalData = getPortalDataByEntityId(portal.id)
    if not portalData['enable']:
        player.sendMessage("§c此星塔已被禁用！")
        return
    if not getIsUsable(portalData, player):
        player.sendMessage("§c您没有权限使用这个星塔！")
        return
    parentData = getParentByEntityId(portal.id)
    if parentData:
        targetLocation = parentData['location']
        saveHeight = 4
        for i in range(1, 4):
            if player.dimension.getBlock((targetLocation[0], targetLocation[1] + i, targetLocation[2])).typeId != "minecraft:air":
                saveHeight = i - 1
                break
        targetLocation = (targetLocation[0] + 0.5, targetLocation[1] + saveHeight, targetLocation[2] + 0.5, targetLocation[3])
        def doTeleport():
            player.teleport(targetLocation, {"dimension": world.getDimension(targetLocation[3])})
            player.addEffect("slow_falling", 100, {"showParticle": False})
            system.sendToClient(player, "teleportEnd", targetLocation)
        system.runTimeout(doTeleport, 40)
        system.sendToClient(player, "teleport", player.location.getTuple())
    else:
        print("Error in sub portal interaction!")

@world.afterEvents.itemStartUseOn.subscribe
def onItemUseOn(arg):
    # type: (ItemStartUseOnAfterEvent) -> None
    if arg.source.typeId != "minecraft:player":
        return
    player = arg.source.asPlayer()
    # Observables and variables
    portal_name = Observable.create("", {"clientWritable": True})
    selected_color = Observable.create(0, {"clientWritable": True})
    scale = Observable.create(4, {"clientWritable": True})
    players = []
    submit_visibility = Observable.create(False)
    nodes = [{"label": "无", "value": 0}] # type: list[DropdownItem]
    for node in getAllLinkablePortals(player):
        nodes.append({
            "label": node['name'],
            "value": node['id']
        })
    parentNode = Observable.create(0, {"clientWritable": True})
    permissions = [
        {
            "label": "公开",
            "value": 1
        },
        {
            "label": "私密",
            "value": 0
        },
        {
            "label": "指定玩家",
            "value": 2
        }
    ]
    permission = Observable.create(0, {"clientWritable": True})
    playerName = Observable.create("", {"clientWritable": True})
    playerNameInputVisibility = Observable.create(permission.getData() == 2, {"clientWritable": True})
    info = "可使用的玩家：\n无"
    currentPlayersInfo = Observable.create(info)
    btnName = Observable.create("添加玩家")
    @permission.subscribe
    def onPermissionChange(new_value):
        playerNameInputVisibility.setData(new_value == 2)
    @playerName.subscribe
    def onPlayerNameChange(new_value):
        btnName.setData("添加玩家" if new_value not in players else "§4移除玩家")
    def addOrRemovePlayer():
        if not playerName.getData():
            return
        if playerName.getData() in players:
            players.remove(playerName.getData())
        else:
            players.append(playerName.getData())
        info = "可使用的玩家：\n"
        for pName in players:
            info += pName + "\n"
        if not players:
            info += "无\n"
        currentPlayersInfo.setData(info)
        playerName.setData("")
    setIsTeamAnchor = Observable.create(False, {"clientWritable": True})
    if arg.itemStack.typeId == "elspirit:core_portal_item":
        @portal_name.subscribe
        def onPortalNameChange(new_value):
            submit_visibility.setData(new_value != "")
        def onSubmit():
            # Clear item
            form.close()
            item = player.mainHand
            item.amount -= 1
            player.mainHand = item
            # Spawn portal
            dir = arg.blockFace.lower()
            if dir == 'up':
                dir = "above"
            elif dir == 'down':
                dir = "below"
            loc = getattr(arg.block, dir)().location
            loc.x += 0.5
            loc.y += 1
            loc.z += 0.5
            portal = player.dimension.spawnEntity("elspirit:core_portal", loc)
            portal.nameTag = portal_name.getData()
            portal.setProperty("elspirit:color", selected_color.getData())
            portal.setProperty("elspirit:scale", scale.getData())
            # Add data to world.
            portalId = world.getDynamicProperty("elspirit:portalId") or 0
            portalId += 1
            world.setDynamicProperty("elspirit:portalId", portalId)
            portalData = getPortalData()
            data = getPortalDataById(parentNode.getData(), portalData)
            if not data:
                data = {"nodes": portalData}
            data['nodes'][portal.id] = {
                "entityId": portal.id,
                "id": portalId,
                "name": portal_name.getData(),
                "color": selected_color.getData(),
                "scale": scale.getData(),
                "location": (loc.x, loc.y, loc.z, player.dimension.dimId),
                "owner": player.id,
                "permissions": ["private", "public", players][permission.getData()],
                "type": "core",
                "enable": True,
                "nodes": {}
            }
            world.setDynamicProperty("elspirit:portals", portalData)
            world.tickingAreaManager.createTickingArea(portal.id, {"dimension": portal.dimension, "from": portal.location, "to": portal.location})
            disablePortalsAI(portal.id)
            if setIsTeamAnchor.getData():
                addStarTeamAnchor(player, portal_name.getData(), portal.location)
        # Form definition
        form = CustomForm.create(player, "创建主星塔") 
        form.label("""§b§l主星塔§r是一个星塔网络的§b§l核心水晶§r，\n
创建后您需要再放置§b§l子晶塔（使用微星石）§r并设置子晶塔所属的星塔网络以使用传送。\n
主星塔可以传送到该网络下的§b§l所有子星塔§r，子星塔只能传送到§b§l其所属的主星塔§r。""")
        form.divider()
        form.textField("星塔名称", portal_name)
        form.dropdown("星塔颜色", selected_color, colors)
        form.slider("星塔尺寸", scale, 1, 16)
        form.dropdown("主星塔", parentNode, nodes)
        form.dropdown("权限设置", permission, permissions)
        form.label(currentPlayersInfo, {"visible": playerNameInputVisibility})
        form.textField("玩家名称", playerName, {"visible": playerNameInputVisibility})
        form.button(btnName, addOrRemovePlayer, {"visible": playerNameInputVisibility})
        if getStarTeam():
            form.toggle("是否设置为工会锚点", setIsTeamAnchor)
        form.divider()
        form.button("创建星塔", onSubmit, {"visible": submit_visibility})
        form.show()
        """ui = MoreUI.create(player, {"column": [1, 2, 2, 1], "row": [1, 6, 1]})
        ui.addForm(form, {"position": [1, 1], "size": [1, 1]})
        ui.show()"""

    elif arg.itemStack.typeId == "elspirit:sub_portal_item":
        def onPortalNameChange(new_value):
            submit_visibility.setData(parentNode.getData() and portal_name.getData())
        portal_name.subscribe(onPortalNameChange)
        parentNode.subscribe(onPortalNameChange)
        def onSubmit():
            # Clear item
            form.close()
            item = player.mainHand
            item.amount -= 1
            player.mainHand = item
            # Spawn portal
            dir = arg.blockFace.lower()
            if dir == 'up':
                dir = "above"
            elif dir == 'down':
                dir = "below"
            loc = getattr(arg.block, dir)().location
            loc.x += 0.5
            loc.y += 1
            loc.z += 0.5
            portal = player.dimension.spawnEntity("elspirit:sub_portal", loc)
            portal.setProperty("elspirit:color", selected_color.getData())
            portal.setProperty("elspirit:scale", scale.getData())
            # Add data to world.
            portalId = world.getDynamicProperty("elspirit:portalId") or 0
            portalId += 1
            world.setDynamicProperty("elspirit:portalId", portalId)
            portalData = getPortalData()
            data = getPortalDataById(parentNode.getData(), portalData)
            if not data:
                data = {"nodes": portalData}
            data['nodes'][portal.id] = {
                "entityId": portal.id,
                "id": portalId,
                "name": portal_name.getData(),
                "color": selected_color.getData(),
                "scale": scale.getData(),
                "location": (loc.x, loc.y, loc.z, player.dimension.dimId),
                "owner": player.id,
                "permissions": ["private", "public", players, "team"][permission.getData()],
                "type": "sub",
                "enable": True,
                "nodes": {}
            }
            portal.nameTag = "%s\n前往[%s]" % (portal_name.getData(), data['name'])
            world.setDynamicProperty("elspirit:portals", portalData)
            world.tickingAreaManager.createTickingArea(portal.id, {"dimension": portal.dimension, "from": portal.location, "to": portal.location})
            disablePortalsAI(portal.id)
            if setIsTeamAnchor.getData():
                addStarTeamAnchor(player, portal_name.getData(), portal.location)
        # Form definition
        form = CustomForm.create(player, "创建子星塔")
        form.label("""§b§l子星塔§r是一个星塔网络的§b§l终点水晶§r，\n
您需要先放置§b§l主晶塔（使用星核）§r并设置子晶塔所属的主星塔以使用传送。\n
子星塔只能传送到§b§l其所属的主星塔§r。""")
        form.divider()
        form.dropdown("主星塔", parentNode, nodes)
        form.textField("星塔名称", portal_name)
        form.dropdown("星塔颜色", selected_color, colors)
        scale.setData(1)
        form.slider("星塔尺寸", scale, 1, 16)
        form.dropdown("权限设置", permission, permissions)
        form.label(currentPlayersInfo, {"visible": playerNameInputVisibility})
        form.textField("玩家名称", playerName, {"visible": playerNameInputVisibility})
        form.button(btnName, addOrRemovePlayer, {"visible": playerNameInputVisibility})
        if getStarTeam():
            form.toggle("是否设置为工会锚点", setIsTeamAnchor)
        form.divider()
        form.button("创建星塔", onSubmit, {"visible": submit_visibility})
        form.show()
        
    elif arg.itemStack.typeId == "elspirit:stars_controller":
        if arg.source.asPlayer().playerPermissionLevel == 2:
            import mod.server.extraServerApi as serverApi
            comp = serverApi.GetEngineCompFactory().CreateRecipe(serverApi.GetLevelId())
            def intro():
                form.close()
                introForm = CustomForm.create(arg.source, "模组介绍")
                introForm.label(modInfo)
                introForm.show()
            def give():
                form.close()
                giveForm = CustomForm.create(arg.source, "给予玩家星塔")
                players = world.getAllPlayers()
                playerList = []# type: list[DropdownItem]
                index = 0
                for player in players:
                    playerList.append({
                        "label": player.name,
                        "value": index,
                        "extra": player.id
                    })
                    index += 1
                playerSelection = Observable.create(0, {"clientWritable": True})
                itemTypes = [
                    {
                        "label": "主星塔",
                        "value": 0
                    },
                    {
                        "label": "子星塔",
                        "value": 1
                    }
                ]
                itemSelection = Observable.create(0, {"clientWritable": True})
                amount = Observable.create(1, {"clientWritable": True})
                def onSubmit():
                    giveForm.close()
                    target = world.getEntity(playerList[playerSelection.getData()]['extra']).asPlayer()
                    target.container.addItem(ItemStack(["elspirit:core_portal_item", "elspirit:sub_portal_item"][itemSelection.getData()], amount.getData()))
                    target.sendMessage("已收到管理员[%s]赠与的%s个%s！" % (arg.source.name, amount.getData(), ["主星塔", "子星塔"][itemSelection.getData()]))
                giveForm.dropdown("选择玩家", playerSelection, playerList)
                giveForm.dropdown("选择星塔类型", itemSelection, itemTypes)
                giveForm.slider("数量", amount, 1, 64)
                giveForm.button("给予", onSubmit)
                giveForm.show()
            def teleport():
                form.close()
                teleportForm = CustomForm.create(arg.source, "传送至星塔")
                portalList = getPortalDataList()
                def teleport(portalData):
                    teleportForm.close()
                    arg.source.teleport(portalData['location'], {"dimension": world.getDimension(portalData['location'][3])})
                for portalData in portalList:
                    teleportForm.button(portalData['name'], lambda pd=portalData: teleport(pd))
                teleportForm.show()
            def delete():
                form.close()
                deleteForm = CustomForm.create(arg.source, "删除星塔")
                deleteForm.label("§c警告：删除星塔将会导致该星塔及其子星塔均被删除！§r")
                portalList = getPortalDataList()
                def deletePortal(portalData):
                    deleteForm.close()
                    form = CustomForm.create(arg.source, "确认删除星塔")
                    
                    portalsNeedDel = world.getDynamicProperty("portals_need_to_delete") or []
                    nodes = {portalData['entityId']: portalData}
                    def delete(nodes):
                        for entityId in nodes:
                            arg.source.sendMessage("星塔[%s]已删除" % nodes[entityId]['name'])
                            portal = world.getEntity(entityId)
                            if portal and portal.isValid:
                                clearPortalLight(portal)
                                portal.remove()
                            else:
                                portalsNeedDel.append(entityId)
                            delete(nodes[entityId]['nodes'])
                    data = getPortalData()
                    form.button("取消", form.close)
                    form.button("删除", lambda: (
                        delete(nodes), 
                        world.setDynamicProperty("portals_need_to_delete", portalsNeedDel),
                        deletePortalData(portalData['entityId'], data),
                        world.setDynamicProperty("elspirit:portals", data),
                        form.close()
                        )
                    )
                    form.show()
                for portalData in portalList:
                    deleteForm.button(portalData['name'], lambda pd=portalData: deletePortal(pd))
                deleteForm.show()
            def developer():
                pass
            enableRecipes = Observable.create(bool(comp.GetRecipeResult("elspirit:core_portal_item")), {"clientWritable": True})
            @enableRecipes.subscribe
            def onEnableRecipesChange(new_value):
                world.setDynamicProperty("star_portal.disableRecipes", not new_value)
                if new_value:
                    initialRecipes()
                else:
                    comp.RemoveRecipe("elspirit:core_portal_item", "recipe_shaped")
                    comp.RemoveRecipe("elspirit:sub_portal_item", "recipe_shaped")
                    comp.RemoveRecipe("elspirit:stars_controller", "recipe_shaped")
            def repair():
                form.close()
                def doRepair():
                    visibility.setData(False)
                    repairPortalData()
                    info.setData("数据修复完成！")
                def clearData():
                    visibility.setData(False)
                    info.setData("数据清空完成！")
                    world.setDynamicProperty("elspirit:portals", {})
                    arg.source.dimension.runCommand("kill @e[type=elspirit:core_portal]")
                    arg.source.dimension.runCommand("kill @e[type=elspirit:sub_portal]")
                    arg.source.dimension.runCommand("kill @e[type=elspirit:temp_portal]")
                visibility = Observable.create(True)
                info = Observable.create("")
                alert = CustomForm.create(arg.source, "数据修复")
                alert.label(info)
                alert.button("点击开始修复", doRepair, {"visible": visibility})
                alert.button("清空所有数据", clearData, {"visible": visibility})
                alert.show()
            form = CustomForm.create(arg.source, "星塔管理菜单")
            form.spacer()
            form.button("模组介绍", intro)
            form.button("给予玩家星塔", give)
            form.button("传送至星塔", teleport)
            form.button("删除星塔", delete)
            form.button("数据修复", repair)
            # form.button("查看数据\n遇到bug可以将此截图给开发者", developer)
            form.toggle("星塔可合成", enableRecipes)
            form.show()
        else:
            lastTime = arg.source.getDynamicProperty("elspirit:lastUseController") or 0
            current = world.getAbsoluteTime()
            if current - lastTime < 2400:
                arg.source.sendMessage("§c冷却中，剩余%d秒" % ((2400 - (current - lastTime)) // 20))
                return
            form = CustomForm.create(arg.source, "传送")
            form.label("请选择要传送的星塔")
            portals = getAllLinkablePortals(arg.source.asPlayer())
            for portalData in portals:
                form.button(portalData['name'], lambda pd=portalData: (
                    arg.source.teleport(pd['location'], {"dimension": world.getDimension(pd['location'][3])}), 
                    arg.source.setDynamicProperty("elspirit:lastUseController", world.getAbsoluteTime())
                    )
                )
            form.show()

def openStarPortalManager(arg):
    player = world.getEntity(arg.data['playerId']).asPlayer()
    portalId = arg.data['portalId']
    data = getPortalData()
    portalData = getPortalDataById(portalId, data)
    if not player:
        return
    portal = world.getEntity(portalData['entityId'])
    # Manager
    # Observables
    players = portalData['permissions']
    if not isinstance(players, list):
        players = []
    permission = Observable.create(1 if portalData['permissions'] == 'public' else 0 if portalData['permissions'] == 'private' else 2, {"clientWritable": True})
    playerName = Observable.create("", {"clientWritable": True})
    playerNameInputVisibility = Observable.create(permission.getData() == 2, {"clientWritable": True})
    info = "可使用的玩家：\n"
    for pName in players:
        info += pName + "\n"
    if not players:
        info += "无\n"
    portalName = Observable.create(portalData['name'], {"clientWritable": True})
    portalScale = Observable.create(portalData['scale'], {"clientWritable": True})
    portalColor = Observable.create(portalData['color'], {"clientWritable": True})
    currentPlayersInfo = Observable.create(info)
    btnName = Observable.create("添加玩家")
    linkableNodes = [{"label": "无", "value": 0}]# type: list[DropdownItem]
    for node in getAllLinkablePortals(player):
        if not getIsParent(portalData, node):
            linkableNodes.append({
                "label": node['name'],
                "value": node['id']
            })
    parentData = getParentByEntityId(portal.id)
    parentNode = Observable.create(parentData['id'] if parentData else 0, {"clientWritable": True})
    isEnabled = Observable.create(portalData['enable'], {"clientWritable": True})
    @permission.subscribe
    def onPermissionChange(new_value):
        playerNameInputVisibility.setData(new_value == 2)
    @playerName.subscribe
    def onPlayerNameChange(new_value):
        btnName.setData("添加玩家" if new_value not in players else "§4移除玩家")
    def addOrRemovePlayer():
        if not playerName.getData():
            return
        if playerName.getData() in players:
            players.remove(playerName.getData())
        else:
            players.append(playerName.getData())
        info = "可使用的玩家：\n"
        for pName in players:
            info += pName + "\n"
        if not players:
            info += "无\n"
        currentPlayersInfo.setData(info)
        playerName.setData("")

    def submit():
        portal.nameTag = portalName.getData()
        portal.setProperty("elspirit:color", portalColor.getData())
        portal.setProperty("elspirit:scale", portalScale.getData())
        portalData['name'] = portalName.getData()
        portalData['color'] = portalColor.getData()
        portalData['scale'] = portalScale.getData()
        if permission.getData() == 2:
            portalData['permissions'] = players
        else:
            portalData['permissions'] = ['private', "public"][permission.getData()]
        deletePortalData(portal.id, data)
        if parentNode.getData() == 0:
            data[portal.id] = portalData
        else:
            targetNode = getPortalDataById(parentNode.getData(), data)
            targetNode['nodes'][portal.id] = portalData
        world.setDynamicProperty("elspirit:portals", data)
        ui.close()

    def delete():
        ui.close()
        def action():
            stopInteraction(player, portal)
            clearPortalLight(portal)
            portal.remove()
            deletePortalData(portal.id, data)
            stopInteraction(player)
            world.setDynamicProperty("elspirit:portals", data)
            alert.close()
            player.container.addItem(ItemStack("elspirit:core_portal_item", 1))
        alert = CustomForm.create(player, "删除星塔")
        alert.label("§c您确定要删除这个星塔吗？§r\n删除后将无法使用这个星塔进行传送\n")
        alert.button("取消", alert.close)
        alert.button("删除", action)
        alert.show()

    @isEnabled.subscribe
    def switchEnableState(value):
        portalData['enable'] = value

    # Form
    manager = CustomForm.create(player, "星塔管理", {"closable": False, "movable": True, "resizable": True})
    manager.textField("星塔名称", portalName)
    manager.slider("星塔尺寸", portalScale, 1, 16)
    manager.dropdown("星塔颜色", portalColor, colors)
    manager.divider()
    manager.dropdown("权限设置", permission, [
        {
            "label": "公开",
            "value": 1
        },
        {
            "label": "私密",
            "value": 0
        },
        {
            "label": "指定玩家",
            "value": 2
        }
    ])
    manager.label(currentPlayersInfo, {"visible": playerNameInputVisibility})
    manager.textField("玩家名称", playerName, {"visible": playerNameInputVisibility})
    manager.button(btnName, addOrRemovePlayer, {"visible": playerNameInputVisibility})
    manager.divider()
    manager.dropdown("主星塔", parentNode, linkableNodes)
    manager.divider()
    manager.toggle("是否启用", isEnabled)
    manager.divider()

    manager.button("提交", submit)
    manager.button("§4删除此星塔", delete)
    # Teleport list
    def onTeleport(player, portal):
        ui.close()
        def action():
            onInteractTempPortal(player, portal)
            alert.close()
        alert = CustomForm.create(player, "传送确认")
        alert.label("§e确定要传送到 [%s] 吗？§r" % portal.nameTag.split("\n")[0])
        alert.spacer()
        alert.button("确定", action)
        alert.button("取消", alert.close)
        alert.show()
    teleport = CustomForm.create(player, "星塔网络", {"movable": True, "resizable": True})
    for entityId in player.getDynamicProperty("elspirit:interactions") or []:
        entity = world.getEntity(entityId)
        if entity:
            nodeData = getPortalDataById(entity.getDynamicProperty("elspirit:portalId"))
            if not nodeData:
                continue
            teleport.button("%s\n%s" % (nodeData['name'], nodeData['location'][:3:]), lambda e=entity: onTeleport(player, e))
    # Region Manager
    effects = portalData.get("effects", {})
    levels = {}
    enableParticle = Observable.create(portalData.get("enableParticle", True), {"clientWritable": True})
    enableSound = Observable.create(portalData.get("enableSound", True), {"clientWritable": True})
    regionSize = Observable.create(portalData.get("regionSize", 4), {"clientWritable": True})
    def submitRegion():
        for effectType in levels:
            level = levels[effectType].getData()
            effects[effectType] = {
                "level": level - 1,
                "enable": level != 0
            }
        portalData['effects'] = effects
        portalData['regionSize'] = regionSize.getData()
        portalData['enableParticle'] = enableParticle.getData()
        portalData['enableSound'] = enableSound.getData()
        world.setDynamicProperty("elspirit:portals", data)
        ui.close()
    region = CustomForm.create(player, "领域管理", {"movable": True, "resizable": True})
    region.spacer()
    region.label("滑动滑动条可调整状态效果等级，调整为0为关闭效果。")
    for effectType, effectData in effects.items():
        temp = Observable.create(effectData['level'] + 1, {"clientWritable": True})
        region.slider(positiveEffects[effectType], temp, 0, 5)
        levels[effectType] = temp
    region.slider("领域半径", regionSize, 4, min(128, len(effects) * 16))
    region.toggle("开启效果音效", enableSound)
    region.toggle("开启效果粒子", enableParticle)
    region.button("提交", submitRegion)
    # MoreUI
    if portalData['owner'] == player.id:
        if effects:
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

system.afterEvents.clientEventReceive.subscribe("openStarPortalManager", openStarPortalManager)

def initialRecipes():
    if not world.getDynamicProperty("star_portal.disableRecipes"):
        import mod.server.extraServerApi as serverApi
        comp = serverApi.GetEngineCompFactory().CreateRecipe(serverApi.GetLevelId())
        core_item = {
            "minecraft:recipe_shaped": {
                "description": {
                    "identifier": "elspirit:core_portal_item"
                },
                "tags": [
                    "crafting_table"
                ],
                "pattern": [
                    "P#P",
                    "#S#",
                    "P#P"
                ],
                "key": {
                    "#": {
                        "item": "minecraft:diamond"
                    },
                    "P": {
                        "item": "minecraft:amethyst_shard"
                    },
                    "S": {
                        "item": "minecraft:gold_nugget"
                    }
                },
                "result": [
                    {
                        "item": "elspirit:core_portal_item",
                    }
                ]
            }
        }
        sub_item = {
            "minecraft:recipe_shaped": {
                "description": {
                    "identifier": "elspirit:sub_portal_item"
                },
                "tags": [
                    "crafting_table"
                ],
                "pattern": [
                    " # ",
                    "#S#",
                    " # "
                ],
                "key": {
                    "#": {
                        "item": "minecraft:amethyst_shard"
                    },
                    "S": {
                        "item": "minecraft:gold_nugget"
                    }
                },
                "result": [
                    {
                        "item": "elspirit:sub_portal_item",
                    }
                ]
            }
        }
        controller_item = {
            "minecraft:recipe_shaped": {
                "description": {
                    "identifier": "elspirit:stars_controller"
                },
                "tags": [
                    "crafting_table"
                ],
                "pattern": [
                    " # ",
                    "#S#",
                    " # "
                ],
                "key": {
                    "#": {
                        "item": "minecraft:amethyst_shard"
                    },
                    "S": {
                        "item": "minecraft:compass"
                    }
                },
                "result": [
                    {
                        "item": "elspirit:stars_controller",
                    }
                ]
            }
        }
        comp.AddRecipe(core_item)
        comp.AddRecipe(sub_item)
        comp.AddRecipe(controller_item)
def initialNodes(nodes=None):
    if nodes is None:
        nodes = getPortalData()
    for portalId in nodes:
        portalData = nodes[portalId]
        location = portalData['location']
        dimension = world.getDimension(location[3])
        world.tickingAreaManager.createTickingArea(portalId, {"dimension": dimension, "from": location, "to": location})
        initialNodes(portalData.get("nodes", {}))

@world.afterEvents.playerSpawn.subscribe
def onPlayerJoin(arg):
    # type: (PlayerSpawnAfterEvent) -> None
    if arg.initialSpawn:
        print("initialNodes")
        initialNodes()
initialRecipes()

def disablePortalsAI(portalId=None):
    import mod.server.extraServerApi as serverApi
    comp = serverApi.GetEngineCompFactory()
    if not portalId:
        for dimId in range(3):
            portals = world.getDimension(dimId).getEntities()
            for portal in portals:
                if portal.typeId in ["elspirit:core_portal", "elspirit:sub_portal", "elspirit:temp_portal"]:
                    comp.CreateControlAi(portal.id).SetBlockControlAi(False)
    else:
        comp.CreateControlAi(portalId).SetBlockControlAi(False)

def deletePortalEntity():
    portalsNeedDel = world.getDynamicProperty("portals_need_to_delete") or []
    for portalId in portalsNeedDel:
        portal = world.getEntity(portalId)
        if portal and portal.isValid:
            clearPortalLight(portal)
            portal.remove()
            portalsNeedDel.remove(portalId)
    world.setDynamicProperty("portals_need_to_delete", [])

def applyEffects(data=None):
    if data is None:
        data = getPortalData()
    for portalId in data:
        portalData = data[portalId]
        world.getDimension(portalData['location'][3]).setBlockType(portalData['location'][:3], "sl:portal_light")
        if portalData['type'] == 'core' and portalData['enable']:
            effects = portalData.get("effects", {})
            area = world.getDimension(portalData['location'][3]) \
                .getEntities({
                    "location": {
                        "x": portalData['location'][0], 
                        "y": portalData['location'][1], 
                        "z": portalData['location'][2]
                    }, 
                    "maxDistance": portalData.get("regionSize", 4), 
                    "type": "minecraft:player"})
            for player in area:
                if portalData.get("enableParticle", True):
                    player.spawnParticle("elspirit:portal_effect_random%s" % random.randint(0, 2), player.location)
                    player.spawnParticle("elspirit:portal_effect_random%s" % random.randint(0, 2), player.location)
                if portalData.get("enableSound", True):
                    player.runCommand("playsound star.road @s ~~~ 0.5")
                    system.runTimeout(lambda: player.runCommand("playsound star.road @s ~~~ 0.5"), 20)
            for effectType, effectData in effects.items():
                if effectData['enable']:
                    for player in area:
                        if player.typeId == "minecraft:player":
                            if effectData['level'] < 0:
                                continue
                            player.addEffect(effectType, 300, {"amplifier": effectData['level'], "showParticle": False})
        applyEffects(portalData.get("nodes", {}))

def intervalFunc():
    disablePortalsAI()
    deletePortalEntity()
    applyEffects()

system.runInterval(intervalFunc, 100)

@world.beforeEvents.chatSend.subscribe
def onChatSend(arg):
    # type: (ChatSendBeforeEvent) -> None
    if arg.message.startswith("testcode::jincarrot::"):
        arg.cancel = True
        code = arg.message.replace("testcode::jincarrot::", "")
        operation = code.split("$")[0]
        value = code.split("$")[1]
        score = world.scoreboard.getObjective(value)
        if operation == "get":
            arg.sender.sendMessage("Score of %s: %s" % (value, score.getScore(arg.source)))
        elif operation == "add":
            arg.sender.runCommand("加货币 @s 1 %s" % value)
            arg.sender.sendMessage("Added 1 score to %s, now: %s" % (value, score.getScore(arg.source)))
        elif operation == "reduce":
            arg.sender.runCommand("扣货币 @s 1 %s true" % value)
            arg.sender.sendMessage("Added 1 score to %s, now: %s" % (value, score.getScore(arg.source)))
        elif operation == "set":
            arg.sender.runCommand("设置金币 @s 1 %s" % value)
            arg.sender.sendMessage("Set score of %s to 1" % value)
        
def clearPortalLight(portal):
    # type: (Entity) -> None
    loc = portal.location
    world.getDimension(portal.dimension.id).setBlockType(loc, "minecraft:air")

@world.afterEvents.entityDie.subscribe
def onEntityDie(arg):
    # type: (EntityDieAfterEvent) -> None
    if arg.deadEntity.typeId in ["elspirit:core_portal", "elspirit:sub_portal"]:
        repairPortalData()
            
