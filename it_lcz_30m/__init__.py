# -*- coding: utf-8 -*-

def classFactory(iface):
    from .main import ITLCZ30m
    return ITLCZ30m(iface)
