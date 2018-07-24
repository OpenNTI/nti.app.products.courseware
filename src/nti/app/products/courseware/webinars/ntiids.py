#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.ntiids.interfaces import INTIIDResolver

logger = __import__('logging').getLogger(__name__)


@interface.implementer(INTIIDResolver)
class _WebinarAssetResolver(object):

    _ext_iface = IWebinarAsset

    def resolve(self, key):
        result = component.queryUtility(self._ext_iface, name=key)
        return result
