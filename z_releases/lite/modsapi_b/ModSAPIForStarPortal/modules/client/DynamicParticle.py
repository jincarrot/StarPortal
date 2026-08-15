# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from ...interfaces.Vector import Vector3
from ...interfaces.ParticleOptions import DynamicParticleOptions, DynamicParticlePattern
from ExpressionString import Variable, ExpressionString

comp = clientApi.GetEngineCompFactory()
drawer = comp.CreateDrawing(clientApi.GetLevelId())


class DynamicParticle:

    def __init__(self, pattern, location, options):
        # type: (DynamicParticlePattern, Vector3, DynamicParticleOptions) -> None
        self.__pattern = pattern
        if self.__pattern.get("x") is None:
            self.__pattern["x"] = 0
        if self.__pattern.get("y") is None:
            self.__pattern["y"] = 0
        if self.__pattern.get("z") is None:
            self.__pattern["z"] = 0
        if self.__pattern.get("color") is None:
            self.__pattern["color"] = (1, 1, 1)
        if isinstance(self.__pattern.get("x"), str):
            self.__pattern["x"] = ExpressionString(self.__pattern["x"])
        if isinstance(self.__pattern.get("y"), str):
            self.__pattern["y"] = ExpressionString(self.__pattern["y"])
        if isinstance(self.__pattern.get("z"), str):
            self.__pattern["z"] = ExpressionString(self.__pattern["z"])
        self.__shouldUpdateColor = False
        temp = []
        for colorItem in self.__pattern["color"]:
            if isinstance(colorItem, str):
                colorItem = ExpressionString(colorItem)
                self.__shouldUpdateColor = True
            temp.append(colorItem)
        self.__pattern["color"] = tuple(temp)
        self.__location = Vector3(location)
        self.__options = options
        self.__mode = options.get("mode", "line")
        self.__maxAmount = options.get("maxAmount", 200)
        self.__interval = options.get("interval", 1)
        self.__shapes = []

        self.__variable = Variable()
        self.__timer = comp.CreateGame(clientApi.GetLevelId()).AddRepeatedTimer(0.05 * self.__interval, self.__update)
        self.__isValid = True

    @property
    def isValid(self):
        return self.__isValid
    
    def remove(self):
        comp.CreateGame(clientApi.GetLevelId()).CancelTimer(self.__timer)
        for shape in self.__shapes:
            shape.Remove()
        self.__isValid = False
    
    def show(self):
        self.__options["visible"] = True
        for shape in self.__shapes:
            shape.SetVisible(True)

    def __update(self):
        # Create new shape
        localVars = {
            "particle_age": 0
        }
        if self.__mode == "point":
            x = self.__location.x + (self.__pattern["x"].eval(self.__variable, localVars) if isinstance(self.__pattern["x"], ExpressionString) else self.__pattern["x"])
            y = self.__location.y + (self.__pattern["y"].eval(self.__variable, localVars) if isinstance(self.__pattern["y"], ExpressionString) else self.__pattern["y"])
            z = self.__location.z + (self.__pattern["z"].eval(self.__variable, localVars) if isinstance(self.__pattern["z"], ExpressionString) else self.__pattern["z"])
            temp = []
            for colorItem in self.__pattern["color"]:
                if isinstance(colorItem, ExpressionString):
                    temp.append(colorItem.eval(self.__variable, localVars))
                else:
                    temp.append(colorItem)
            color = tuple(temp)
            shape = drawer.AddLineShape((x, y, z), (x, y + 0.01, z), color)
        else:
            if len(self.__shapes) == 0:
                x = self.__location.x + (self.__pattern["x"].eval(self.__variable, localVars) if isinstance(self.__pattern["x"], ExpressionString) else self.__pattern["x"])
                y = self.__location.y + (self.__pattern["y"].eval(self.__variable, localVars) if isinstance(self.__pattern["y"], ExpressionString) else self.__pattern["y"])
                z = self.__location.z + (self.__pattern["z"].eval(self.__variable, localVars) if isinstance(self.__pattern["z"], ExpressionString) else self.__pattern["z"])
                temp = []
                for colorItem in self.__pattern["color"]:
                    if isinstance(colorItem, ExpressionString):
                        temp.append(colorItem.eval(self.__variable, localVars))
                    else:
                        temp.append(colorItem)
                color = tuple(temp)
                shape = drawer.AddLineShape((x, y-0.01, z), (x, y, z), color)
            else:
                x0, y0, z0 = self.__shapes[-1].GetEndPos()
                x1 = self.__location.x + (self.__pattern["x"].eval(self.__variable, localVars) if isinstance(self.__pattern["x"], ExpressionString) else self.__pattern["x"])
                y1 = self.__location.y + (self.__pattern["y"].eval(self.__variable, localVars) if isinstance(self.__pattern["y"], ExpressionString) else self.__pattern["y"])
                z1 = self.__location.z + (self.__pattern["z"].eval(self.__variable, localVars) if isinstance(self.__pattern["z"], ExpressionString) else self.__pattern["z"])
                temp = []
                for colorItem in self.__pattern["color"]:
                    if isinstance(colorItem, ExpressionString):
                        temp.append(colorItem.eval(self.__variable, localVars))
                    else:
                        temp.append(colorItem)
                color = tuple(temp)
                shape = drawer.AddLineShape((x0, y0, z0), (x1, y1, z1), color)
        # Update old shapes
        if self.__shouldUpdateColor:
            for s in self.__shapes[:-1]:
                localVars = {
                    "particle_age": self.__interval * (len(self.__shapes) - self.__shapes.index(s) - 1)
                }
                temp = []
                for colorItem in self.__pattern["color"]:
                    if isinstance(colorItem, ExpressionString):
                        temp.append(colorItem.eval(self.__variable, localVars))
                    else:
                        temp.append(colorItem)
                color = tuple(temp)
                s.SetColor(color)
        # Set visibility
        if not self.__options.get("visible", True):
            shape.SetVisible(False)
        self.__shapes.append(shape)
        # Remove old shapes if exceed max amount
        if len(self.__shapes) > self.__maxAmount:
            self.__shapes[0].Remove()
            self.__shapes.pop(0)


    

