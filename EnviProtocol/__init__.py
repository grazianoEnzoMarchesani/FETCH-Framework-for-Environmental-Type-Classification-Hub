# -*- coding: utf-8 -*-

def classFactory(iface):
    from .main import EnviProtocol
    return EnviProtocol(iface)
