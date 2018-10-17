#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from collections import defaultdict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit)
class AbstractIMSWebContent(object):

    _dependencies = defaultdict(list)

    def __init__(self, context):
        self.context = context

    @Lazy
    def dependencies(self):
        return self._dependencies

    @Lazy
    def intids(self):
        intids = component.getUtility(IIntIds)
        return intids

    @Lazy
    def identifier(self):
        return self.intids.queryId(self.context)
    __name__ = identifier

    def export(self):
        raise NotImplementedError
