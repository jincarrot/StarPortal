# -*- coding: utf-8 -*-
from typing import Literal, TypedDict
from Vector import Vector3
from ..modules.client.ExpressionString import ExpressionString

class ParticleBindEntityOptions(TypedDict):
    bone: str
    offset: Vector3
    rotate: Vector3

class DynamicParticlePattern(TypedDict):
    x: ExpressionString | int | float
    y: ExpressionString | int | float
    z: ExpressionString | int | float
    color: tuple[ExpressionString | float, ExpressionString | float, ExpressionString | float]
    """Color of this pattern, in RGB format. Each channel can be a number between 0 and 1, or an expression string that evaluates to a number between 0 and 1."""

class DynamicParticleOptions(TypedDict):
    mode: Literal["point", 'line']
    """粒子模式，为“point”会以多个点的形式绘制，为“line”会以多个短线段形式绘制。默认为'line'"""
    visible: bool
    """若设为false，则必须使用接口手动显示。默认为'true'"""
    interval: int
    """粒子更新的时间间隔，单位为tick，间隔时间越高性能越好。默认为1"""
    maxAmount: int
    """粒子最大数量，超过这个数量后会开始删除旧的粒子。默认为200"""

