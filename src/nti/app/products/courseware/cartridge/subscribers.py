#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from zope import component

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridgeExtension

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class CanvasFilesMeta(list):
    pass


def canvas_files_meta(content_unit):
    files_meta = component.queryUtility(IIMSCommonCartridgeExtension, name='files_meta')
    if files_meta is None:
        files_meta = CanvasFilesMeta()
        gsm = component.getGlobalSiteManager()
        gsm.registerUtility(files_meta, IIMSCommonCartridgeExtension, name='files_meta')
    files_meta.append(content_unit)
