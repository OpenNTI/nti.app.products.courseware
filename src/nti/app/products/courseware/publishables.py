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

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.publishing.interfaces import IPublishable
from nti.publishing.interfaces import IPublishables

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPublishables)
class CourseCatalogPublishables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def _process_course(self, course, result):
        # assets
        container = IPresentationAssetContainer(course)
        for asset in container.assets():
            if IPublishable.providedBy(asset):
                result.append(asset)
        # nodes
        def _recur(node):
            if IPublishable.providedBy(node):
                result.append(node)
            for child in node.values():
                _recur(child)
        outline = course.Outline
        if outline is not None:
            _recur(outline)
        # forums
        for forum in course.Discussions.values():
            for topic in forum.values():
                if IPublishable.providedBy(topic):
                    result.append(topic)
        return result

    def iter_objects(self):
        result = []
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is not None:
            for entry in catalog.iterCatalogEntries():
                course = ICourseInstance(entry)
                self._process_course(course, result)
        return result
