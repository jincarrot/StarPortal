# -*- coding: utf-8 -*-
class Promise:
    """
    This is not equals to promise in js.
    """
    
    def __init__(self, type=None):
        """
        Create promise.
        
        :param callback: Defines when this promise finished.
        """

    def _run(self, arg):
        if self.__callback:
            if arg:
                self.__callback(arg)
            else:
                self.__callback()

    def then(self, callback):
        self.__callback = callback

