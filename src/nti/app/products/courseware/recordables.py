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

from nti.recorder.interfaces import IRecordable
from nti.recorder.interfaces import IRecordables

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IRecordables)
class CourseCatalogRecordables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def _process_course(self, course, result):
        # assets
        container = IPresentationAssetContainer(course)
        for asset in container.assets():  # pylint: disable=too-many-function-args
            if IRecordable.providedBy(asset):
                result.append(asset)
        # nodes
        def _recur(node):
            if IRecordable.providedBy(node):
                result.append(node)
            for child in node.values():
                _recur(child)
        outline = course.Outline
        if outline is not None:
            _recur(outline)
        return result

    def iter_objects(self):
        result = []
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is not None:
            for entry in catalog.iterCatalogEntries():
                course = ICourseInstance(entry)
                self._process_course(course, result)
        return result
