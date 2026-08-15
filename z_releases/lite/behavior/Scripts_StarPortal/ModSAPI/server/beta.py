# -*- coding: utf-8 -*-

from system import systems

world = systems.world
system = systems.system


ItemStack = systems.modules.ItemStack
MolangVariableMap = systems.modules.MolangVariableMap


StructureSaveMode = systems.enums.StructureSaveMode
StructureMirrorAxis = systems.enums.StructureMirrorAxis
StructureRotation = systems.enums.StructureRotation
StructureAnimationMode = systems.enums.StructureAnimationMode
PlayerPermissionLevel = systems.enums.PlayerPermissionLevel

EquipmentSlot = systems.enums.EquipmentSlot

EntityEquippableComponent = systems.components.EntityEquippableComponent
EntityInventoryComponent = systems.components.EntityInventoryComponent