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

from nti.contenttypes.completion.interfaces import ICompletables
from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICompletables)
class CourseCatalogCompletables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def iter_objects(self):
        result = []
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is not None:
            for entry in catalog.iterCatalogEntries():
                course = ICourseInstance(entry, None)
                if ICompletableItem.providedBy(course):
                    result.append(course)
        return result
