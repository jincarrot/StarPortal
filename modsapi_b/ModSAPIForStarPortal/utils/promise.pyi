# -*- coding: utf-8 -*-
from typing import TypeVar, Generic, Callable, overload

T = TypeVar("T")

class Promise(Generic[T]):
    """
    Promise.
    """
    def __init__(self, type: T=None) -> Promise[T]:
        pass

    def then(self, callback: Callable[[T], None]) -> None:
        """After the promise is finished, run the callback function."""
        pass

