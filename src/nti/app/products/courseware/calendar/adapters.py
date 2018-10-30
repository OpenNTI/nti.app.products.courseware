#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.model import CourseCalendar

from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseCalendar)
def _CourseCalendarFactory(course, create=True):
    result = None
    KEY = u'CourseCalendar'
    annotations = IAnnotations(course)
    try:
        result = annotations[KEY]
    except KeyError:
        if create:
            result = CourseCalendar()
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
            connection = IConnection(course, None)
            if connection is not None:
                # pylint: disable=too-many-function-args
                connection.add(result)
    return result


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def _CourseCalendarPathAdapter(context, request):
    return _CourseCalendarFactory(context)
