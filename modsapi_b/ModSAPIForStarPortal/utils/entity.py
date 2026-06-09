# -*- coding: utf-8 -*-
from ..interfaces.EntityOptions import EntityQueryOptions, EntityQueryPropertyValue
import mod.server.extraServerApi as serverApi
from ..interfaces.Vector import Vector3
from ..config import Namespace
import random

def getEntityFilterBySelector(selector, entity=None):
        # type: (str, any) -> EntityQueryOptions
        """Returns entities that match the given selector."""
        origin = Vector3((0, 0, 0) if not entity else entity.location)
        volume = Vector3((-1, -1, -1))
        data = {} # type: EntityQueryOptions
        selectorType = selector[1]
        if selectorType == 'p':
            data['type'] = 'minecraft:player'
            data['closest'] = 1
        elif selectorType == 'a':
            data['type'] = 'minecraft:player'
        elif selectorType == 'r':
            data['location'] = {"x": random.randint(-2147483648, 2147483647), "y": random.randint(-2147483648, 2147483647), "z": random.randint(-2147483648, 2147483647)}
            data['closest'] = 1
        elif selectorType == 's':
            data['location'] = entity.location if entity else {"x": 0, "y": 0, "z": 0}
            data['closest'] = 1
        # Process selector arguments
        selectorArgs = selector[3:-1].split(',')
        scoreArgs = {}
        isScoreOption = False
        for arg in selectorArgs:
            key, value = arg.split('=', 1)
            if isScoreOption:
                if value[-1] == "}":
                    value = value[:-1]
                    isScoreOption = False
                scoreArgs[key] = value
                continue
            if key == 'type':
                if value[0] == "!":
                    if 'exludeTypes' not in data:
                        data['excludeTypes'] = []
                    data['excludeTypes'].append(value[1:])
                elif not data.get("type"):
                    data['type'] = value
            elif key == 'name':
                if value[0] == "!":
                    if 'excludeNames' not in data:
                        data['excludeNames'] = []
                    data['excludeNames'].append(value[1:])
                else:
                    data['name'] = value
            elif key == 'tag':
                if value[0] == "!":
                    if 'excludeTags' not in data:
                        data['excludeTags'] = []
                    data['excludeTags'].append(value[1:])
                elif 'tags' not in data:
                    data['tags'] = []
                data['tags'].append(value)
            elif key == 'r':
                data['maxDistance'] = int(value)
            elif key == 'rm':
                data['minDistance'] = int(value)
            elif key == "c":
                if int(value) >= 0:
                    data['closest'] = int(value)
                else:
                    data['farthest'] = -int(value)
            elif key == "x":
                origin.x = int(value)
            elif key == "y":
                origin.y = int(value)
            elif key == "z":
                origin.z = int(value)
            elif key == "dx":
                volume.x = int(value)
            elif key == "dy":
                volume.y = int(value)
            elif key == "dz":
                volume.z = int(value)
            elif key == "rx":
                data['maxHorizontalRotation'] = int(value)
            elif key == "rxm":
                data['minHorizontalRotation'] = int(value)
            elif key == "ry":
                data['maxVerticalRotation'] = int(value)
            elif key == "rym":
                data['minVerticalRotation'] = int(value)
            elif key == 'scores':
                # scores={a=1,b=2..10,c=..2}
                isScoreOption = True
                scoreArgs[value.replace("{", "").split("=")[0]] = value.split("=")[1]
        for scoreArgKey in scoreArgs:
            scoreArgValue = scoreArgs[scoreArgKey]
            scoreOption = {"objective": scoreArgKey}
            if scoreArgValue[0] == "!":
                scoreOption['exclude'] = True
                scoreArgValue = scoreArgValue[1:]
            if ".." in scoreArgValue:
                minScore, maxScore = scoreArgValue.split("..")
                if minScore:
                    scoreOption['minScore'] = int(minScore)
                if maxScore:
                    scoreOption['maxScore'] = int(maxScore)
            else:
                scoreOption['minScore'] = int(scoreArgValue)
                scoreOption['maxScore'] = int(scoreArgValue)
            if 'scoreOptions' not in data:
                data['scoreOptions'] = []
            data['scoreOptions'].append(scoreOption)
        data['location'] = origin
        if volume.x > 0 and volume.y > 0 and volume.z > 0:
            data['volume'] = volume
        return data

def queryEntities(entityFilter):
    # type: (EntityQueryOptions) -> list
    """Gets entities that match the given filter."""
    from ..modules.server.Entity import Entity
    coreSys = serverApi.GetSystem(Namespace, "core") 
    entities = coreSys.entities # type: list[Entity]
    result = []
    for entity in entities:
        if entity.isValid:
            if entityFilter.get("type", None):
                if entity.typeId != entityFilter['type']:
                    continue
            if entityFilter.get("name", None):
                if entity.nameTag != entityFilter['name']:
                    continue
            if entityFilter.get("tags", None):
                tags = entityFilter['tags']
                currentTags = entity.getTags()
                if not all(tag in currentTags for tag in tags):
                    continue
            if entityFilter.get("families", None):
                families = entityFilter['families']
                currentFamilies = entity.getFamilies()
                if not all(family in currentFamilies for family in families):
                    continue
            if entityFilter.get("gameMode", None):
                if entity.typeId != 'minecraft:player' or entity.asPlayer().getGameMode() != entityFilter['gameMode']:
                    continue
            if entityFilter.get("excludeFamilies", None):
                excludeFamilies = entityFilter['excludeFamilies']
                currentFamilies = entity.getFamilies()
                if any(family in currentFamilies for family in excludeFamilies):
                    continue
            if entityFilter.get("excludeTypes", None):
                if entity.typeId in entityFilter['excludeTypes']:
                    continue
            if entityFilter.get("excludeNames", None):
                if entity.nameTag in entityFilter['excludeNames']:
                    continue
            if entityFilter.get("excludeTags", None):
                excludeTags = entityFilter['excludeTags']
                currentTags = entity.getTags()
                if any(tag in currentTags for tag in excludeTags):
                    continue
            if entityFilter.get("excludeGameModes", None):
                if entity.typeId == 'minecraft:player':
                    if entity.asPlayer().getGameMode() in entityFilter['excludeGameModes']:
                        continue
            if entityFilter.get("maxHorizontalRotation", None):
                rot = entity.getRotation()
                if rot.x > entityFilter['maxHorizontalRotation']:
                    continue
            if entityFilter.get("minHorizontalRotation", None):
                rot = entity.getRotation()
                if rot.x < entityFilter['minHorizontalRotation']:
                    continue
            if entityFilter.get("maxVerticalRotation", None):
                rot = entity.getRotation()
                if rot.y > entityFilter['maxVerticalRotation']:
                    continue
            if entityFilter.get("minVerticalRotation", None):
                rot = entity.getRotation()
                if rot.y < entityFilter['minVerticalRotation']:
                    continue
            if entityFilter.get("minLevel", None):
                if entity.typeId == 'minecraft:player':
                    if entity.asPlayer().level < entityFilter['minLevel']:
                        continue
            if entityFilter.get("maxLevel", None):
                if entity.typeId == 'minecraft:player':
                    if entity.asPlayer().level > entityFilter['maxLevel']:
                        continue
            # Distance check
            location = Vector3((0, 0, 0))
            if entityFilter.get("location", None):
                location = Vector3(entityFilter["location"])
            if entityFilter.get("maxDistance", None):
                if (location - entity.location).distance > entityFilter["maxDistance"]:
                    continue
            if entityFilter.get("minDistance", None):
                if (location - entity.location).distance < entityFilter["minDistance"]:
                    continue
            if entityFilter.get("volume", None):
                volume = Vector3(entityFilter['volume'])
                x = entity.location.x - location.x
                y = entity.location.y - location.y
                z = entity.location.z - location.z
                if abs(x) > volume.x or abs(y) > volume.y or abs(z) > volume.z:
                    continue
            # Score check
            if entityFilter.get("scoreOptions", None):
                from system import systems
                scoreOptions = entityFilter['scoreOptions']
                matched = True
                for scoreOption in scoreOptions:
                    score = systems.world.scoreboard.getObjective(scoreOption['objective']).getScore(entity)
                    if not score:
                        matched = False
                    if scoreOption.get("exclude", False):
                        if scoreOption.get("minScore", -2147483648) < score < scoreOption.get("maxScore", 2147483647):
                            matched = False
                            break
                    else:
                        if scoreOption.get("minScore", None) is not None and score < scoreOption['minScore']:
                            matched = False
                            break
                        if scoreOption.get("maxScore", None) is not None and score > scoreOption['maxScore']:
                            matched = False
                            break
                if not matched:
                    continue
            # Property check
            if entityFilter.get("propertyOptions", None):
                propertyOptions = entityFilter['propertyOptions']
                matched = True
                for propertyOption in propertyOptions:
                    propertyValue = entity.getProperty(propertyOption['propertyId'])
                    if propertyValue is None:
                        matched = False
                        break
                    if propertyOption.get("exclude", False):
                        if EntityQueryPropertyValue(propertyOption['value']) == propertyValue:
                            matched = False
                            break
                    else:
                        if not(EntityQueryPropertyValue(propertyOption['value']) == propertyValue):
                            matched = False
                            break
                if not matched:
                    continue
            result.append(entity)
    # Detect amount
    location = Vector3(entityFilter.get("location", {"x": 0, "y": 0, "z": 0}))
    if entityFilter.get("closest", None):
        result.sort(key=lambda e: abs((location - e.location).distance))
        result = result[:entityFilter['closest']]
    if entityFilter.get("farthest", None):
        result.sort(key=lambda e: abs((location - e.location).distance), reverse=True)
        result = result[:entityFilter['farthest']]
    if entityFilter.get("closest") and entityFilter.get("farthest"):
        result = []
    return result
