import mod.server.extraServerApi as serverApi
from ..modules.server.World import World
from ..modules.server.System import System
from modules import Modules
from enums import Enums
from components import Components

import typing
class systems:

    @property
    def world() -> World:
        """World"""

    @property
    def system() -> System:
        """System"""

    @property
    def modules() -> Modules:
        """Modules"""

    @property
    def enums() -> Enums:
        """Enums"""

    @property
    def components() -> Components: 
        """Components"""

    @property
    def clientCallable() -> typing.Callable[[typing.Callable[..., None]], None]:
        """A decorator that allows a server function to be called by the client."""
        pass