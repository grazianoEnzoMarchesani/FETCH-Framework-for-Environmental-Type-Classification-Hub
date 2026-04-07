# -*- coding: utf-8 -*-

def classFactory(iface):
    from .main import FETCH
    return FETCH(iface)
