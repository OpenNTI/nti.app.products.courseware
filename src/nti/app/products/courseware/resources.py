#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent

from nti.contentfolder.model import RootFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from .interfaces import ICourseRootFolder

@interface.implementer(ICourseRootFolder)
class CourseRootFolder(RootFolder):
    pass

@component.adapter(ICourseInstance)
@interface.implementer(ICourseRootFolder)
def _course_resources(course, create=True):
    result = None
    annotations = IAnnotations(course)
    try:
        KEY = 'resources'
        result = annotations[KEY]
    except KeyError:
        if create:
            result = CourseRootFolder(name="resources")
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
    return result

def _resources_for_course_path_adapter(context, request):
    course = ICourseInstance(context)
    return _course_resources(course)

@component.adapter(ICourseInstance, IObjectAddedEvent)
def _on_course_added(course, event):
    _course_resources(course)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, event):
    root = _course_resources(course, False)
    if root is not None:
        root.clear()
        