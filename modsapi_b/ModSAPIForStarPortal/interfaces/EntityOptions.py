# -*- coding: utf-8 -*-
# from typing import List, Dict, Union
from Vector import *
from ..enums.Entity import *
from ..enums.Game import *
# from ..Classes.Entity import *
import math
import mod.server.extraServerApi as serverApi
from ..utils.system import systems

comp = serverApi.GetEngineCompFactory()

class EntityQueryScoreOptions:
    """Contains additional options for filtering players based on their score for an objective."""

    def __init__(self, data):
        self.exclude = data['exclude'] if 'exclude' in data else False
        """If set to true, entities and players within this score range are excluded from query results."""
        self.objective = data['objective'] if 'objective' in data else ""
        """Identifier of the scoreboard objective to filter on."""
        self.minScore = data['minScore'] if 'minScore' in data else -2147483648
        """If defined, only players that have a score equal to or over minScore are included."""
        self.maxScore = data['maxScore'] if 'maxScore' in data else 2147483647
        """If defined, only players that have a score equal to or under maxScore are included."""

class EntityQueryPropertyValue:

    def __init__(self, data):
        self.data = data
        if type(self.data).__name__ != 'dict':
            self.data = {"equals": self.data}

    def __eq__(self, other):
        if "equals" in self.data:
            return other == self.data['equals']
        if "lessThan" in self.data:
            return other < self.data['lessThan']
        if "greaterThan" in self.data:
            return other > self.data['greaterThan']
        if "lessThanOrEquals" in self.data:
            return other <= self.data['lessThanOrEquals']
        if "greaterThanOrEquals" in self.data:
            return other >= self.data['greaterThanOrEquals']
        if "notEquals" in self.data:
            return other != self.data['notEquals']
        if "lowerBound" in self.data and "upperBound" in self.data:
            return other >= self.data['lowerBound'] and other <= self.data['upperBound']
        return False
        
    
class EntityQueryPropertyOptions:
    """"""

    def __init__(self, data):
        self.exlude = data.get("exlude", False)
        self.propertyId = data['propertyId']
        self.value = data.get("value", None)


class EntityFilter(object):
    """
    Contains options for filtering entities.
    """

    def __init__(self, data):
        self.excludeFamilies = data['excludeFamilies'] if 'excludeFamilies' in data else []
        """If this value is set, this event will only fire for entities that do not match the entity families within this collection."""
        self.excludeTypes = data['excludeTypes'] if 'excludeTypes' in data else []
        """If this value is set, this event will only fire if the impacted entities' type matches this parameter."""
        self.excludeGameModes = data['excludeGameModes'] if 'excludeGameModes' in data else [] # type: list[GameMode]
        """If this value is set, this event will only fire if the impacted entities' game mode matches this parameter."""
        self.excludeNames = data['excludeNames'] if 'excludeNames' in data else []
        """If this value is set, this event will only fire if the impacted entities' name matches this parameter."""
        self.excludeTags = data['excludeTags'] if 'excludeTags' in data else []
        """If this value is set, this event will only fire if the impacted entities' tags match this parameter."""
        self.families = data['families'] if 'families' in data else []
        """If this value is set, this event will only fire if the impacted entities' family matches this parameter."""
        self.gameMode = data['gameMode'] if 'gameMode' in data else None # type: GameMode
        """If this value is set, this event will only fire if the impacted entities' game mode matches this parameter."""
        self.maxHorizontalRotation = data['maxHorizontalRotation'] if 'maxHorizontalRotation' in data else None
        """If this value is set, this event will only fire if the impacted entities' max horizontal rotation matches this parameter."""
        self.maxLevel = data['maxLevel'] if 'maxLevel' in data else None
        """If this value is set, this event will only fire if the impacted entities' level matches this parameter."""
        self.maxVerticalRotation = data['maxVerticalRotation'] if 'maxVerticalRotation' in data else None
        """If this value is set, this event will only fire if the impacted entities' max vertical rotation matches this parameter."""
        self.minLevel = data['minLevel'] if 'minLevel' in data else None
        """If this value is set, this event will only fire if the impacted entities' level matches this parameter."""
        self.minHorizontalRotation = data['minHorizontalRotation'] if 'minHorizontalRotation' in data else None
        """If this value is set, this event will only fire if the impacted entities' min horizontal rotation matches this parameter."""
        self.minVerticalRotation = data['minVerticalRotation'] if 'minVerticalRotation' in data else None
        """If this value is set, this event will only fire if the impacted entities' min vertical rotation matches this parameter."""
        self.name = data['name'] if 'name' in data else ""
        """If this value is set, this event will only fire if the impacted"""
        self.propertyOptions = data['propertyOptions'] if 'propertyOptions' in data else None # type: list[EntityQueryPropertyOptions]
        """If this value is set, this event will only fire if the impacted entities' property options match this parameter."""
        self.scoreOptions = data['scoreOptions'] if 'scoreOptions' in data else None # type: list[EntityQueryScoreOptions]
        """If this value is set, this event will only fire if the impacted entities' score options match this parameter."""
        self.tags = data['tags'] if 'tags' in data else []
        """If this value is set, this event will only fire if the impacted entities' tags match this parameter."""
        self.type = data['type'] if 'type' in data else ""


class EntityEventOptions(object):
    """
    Contains optional parameters for registering an entity event.
    """

    def __init__(self, data):
        self.__entities = data['entities'] if 'entities' in data else []
        """If this value is set, this event will only fire for entities that match the entities within this collection."""
        self.__entityTypes = data['entityTypes'] if 'entityTypes' in data else []
        """If this value is set, this event will only fire if the impacted entities' type matches this parameter."""

    @property
    def entities(self):
        """If this value is set, this event will only fire for entities that match the entities within this collection."""
        return self.__entities

    @entities.setter
    def entities(self, data):
        self.__entities = data

    @property
    def entityTypes(self):
        # type: () -> list[str]
        """If this value is set, this event will only fire if the impacted entities' type matches this parameter."""
        return self.__entityTypes

    @entityTypes.setter
    def entityTypes(self, data):
        # type: (list[str]) -> None
        self.__entityTypes = data


class EntityQueryOptions(EntityFilter):
    """
    Contains options for selecting entities within an area.
    """

    def __init__(self, data):
        # type: (dict) -> None
        self.data = data
        EntityFilter.__init__(self, data)
        self.closest = data['closest'] if 'closest' in data else -1
        # type: int
        """
        Limits the number of entities to return, opting for the closest N entities as specified by this property.
        The location value must also be specified on the query options object.
        """
        self.farthest = data['farthest'] if 'farthest' in data else -1
        # type: int
        """
        Limits the number of entities to return, opting for the farthest N entities as specified by this property. 
        The location value must also be specified on the query options object.
        """
        self.location = Vector3(data['location']) if 'location' in data else Vector3({})
        # type: Vector3
        """
        Adds a seed location to the query that is used in conjunction with closest, farthest, limit, volume, and distance properties.
        """
        self.maxDistance = data['maxDistance'] if 'maxDistance' in data else -1
        # type: int
        """
        If specified, includes entities that are less than this distance away from the location specified in the location property.
        """
        self.minDistance = data['minDistance'] if 'minDistance' in data else -1
        # type: int
        """
        If specified, includes entities that are least this distance away from the location specified in the location property.
        """
        self.volume = Vector3(data['volume']) if 'volume' in data else None
        # type: Vector3
        """
        In conjunction with location, specified a cuboid volume of entities to include.
        """


class EntityEffectOptions(object):
    """
    Contains additional options for entity effects.
    """

    def __init__(self, data):
        self.__data = data
        if type(self.__data).__name__ != 'dict':
            self.__data = {}
        self.amplifier = self.__data['amplifier'] if 'amplifier' in self.__data else 0
        self.showParticle = self.__data['showParticle'] if 'showParticle' in self.__data else True


class EntityApplyDamageByProjectileOptions(object):
    """
    Additional options for when damage has been applied via a projectile.
    """

    def __init__(self, data):
        self.damagingProjectile = data['damagingProjectile']
        self.damagingEntity = data['damagingEntity'] if 'damagingEntity' in data else None
        """Optional entity that caused the damage."""


class EntityApplyDamageOptions(object):
    """
    Additional descriptions and metadata for a damage event.
    """
    def __init__(self, data):
        self.cause = data['cause'] if 'cause' in data else 'none'
        """Underlying cause of the damage."""
        self.cause = getattr(EntityDamageCause, self.cause)
        self.damagingEntity = data['damagingEntity'] if 'damagingEntity' in data else None
        """Optional entity that caused the damage."""


class EntityRaycastOptions(EntityFilter):
    """
    Returns the first intersecting block from the direction that this entity is looking at.
    """

    def __init__(self, data):
        EntityFilter.__init__(self, data)
        self.ignoreBlockCollision =  data['ignoreBlockCollision'] if 'ignoreBlockCollision' in data else False
        """Whether to ignore block collision."""
        self.includeLiquidBlocks = data['includeLiquidBlocks'] if 'includeLiquidBlocks' in data else False
        """Whether to include liquid blocks in the raycast."""
        self.includePassableBlocks = data['includePassableBlocks'] if 'includePassableBlocks' in data else False
        """Whether to include passable blocks in the raycast."""
        self.maxDistance = data['maxDistance'] if 'maxDistance' in data else 16


class SpawnEntityOptions(object):
    """
    Contains additional options for spawning an Entity.
    """

    def __init__(self, data):
        self.initialPersistence = data['initialPersistence'] if 'initialPersistence' in data else False# type: bool
        """Optional boolean which determines if this entity should persist in the game world. Persistence prevents the entity from automatically despawning."""
        self.initialRotation = data['initialRotation'] if 'initialRotation' in data else 0 # type: int
        """Optional initial rotation, in degrees, to set on the entity when it spawns."""
        self.spawnEvent = data['spawnEvent'] if 'spawnEvent' in data else None # type： str
        """Optional spawn event to send to the entity after it is spawned."""


class PlayerSoundOptions(object):
    """
    Additional options for how a sound plays for a player.
    """

    def __init__(self, data):
        self.location = data['location'] if 'location' in data else (0, 0, 0) # type: Vector3
        """Location of the sound; if not specified, the sound is played near a player."""
        self.location = Vector3(self.location)
        self.pitch = data['pitch'] if 'pitch' in data else 1.0
        """Optional pitch of the sound."""
        self.volume = data['volume'] if 'volume' in data else 1.0
        """Optional volume of the sound."""


class MusicOptions(object):
    """
    Additional options for how a sound plays for a player.
    """

    def __init__(self, data):
        self.loop = data['loop'] if 'loop' in data else False
        """If set to true, this music track will play repeatedly."""
        self.fade = data['fade'] if 'fade' in data else 1.0
        """Specifies a fade overlap for music at the end of play."""
        self.volume = data['volume'] if 'volume' in data else 1.0
        """Relative volume level of the music."""
