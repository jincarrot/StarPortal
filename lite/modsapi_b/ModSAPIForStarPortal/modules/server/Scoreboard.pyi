# -*- coding: utf-8 -*-
# from typing import Union, Dict
from Entity import Entity

class ScoreboardScoreInfo:
    """Contains a pair of a scoreboard participant and its respective score."""
    
    @property
    def participant(self):
        # type: () -> ScoreboardIdentity
        pass
    
    @property
    def score(self):
        # type: () -> int
        pass

class ScoreboardIdentity(object):
    """
    Contains an identity of the scoreboard item.
    """
    @property
    def displayName(self):
        # type: () -> str
        pass
    
    @property
    def id(self):
        # type: () -> str
        pass
    
    @property
    def type(self):
        # type: () -> str
        pass
    
    def getEntity(self):
        # type: () -> Entity | None
        pass


class ScoreboardObjective(object):
    """
    Contains information about a scoreboard objective.
    """
    @property
    def id(self):
        # type: () -> str
        pass
    
    @property
    def displayName(self):
        # type: () -> str
        pass
    
    @property
    def isValid(self) -> bool:
        pass
    
    def addScore(self, participate, scoreToAdd):
        # type: (Entity | str, int) -> int
        """
        Adds a score to the given participant and objective.
        """
    
    def getScore(self, participate):
        # type: (Entity | str | ScoreboardIdentity) -> int | None
        """Returns a specific score for a participant."""
        
    def getScores(self):
        # type: () -> list[ScoreboardScoreInfo]
        """Returns specific scores for this objective for all participants."""
        

    def getParticipants(self):
        # type: () -> list[ScoreboardIdentity]
        pass


class Scoreboard(object):
    """
    Contains objectives and participants for the scoreboard.
    """

    @staticmethod
    def addObjective(objectiveId, displayName=""):
        # type: (str, str) -> ScoreboardObjective
        """
        Adds a new objective to the scoreboard.
        """
       
    
    @staticmethod
    def getObjective(objectiveId):
        # type: (str) -> ScoreboardObjective | None
        """
        Returns a specific objective (by id).
        """
        
    
    def clearObjectiveAtDisplaySlot(self, displaySlotId):
        # type: (str) -> None
        """
        Clears the objective that occupies a display slot.

        Note: this method can return object only when try to clear sidebar
        """
    
    @staticmethod
    def getObjectives():
        # type: () -> list[ScoreboardObjective]
        """
        Returns all defined objectives.
        """

