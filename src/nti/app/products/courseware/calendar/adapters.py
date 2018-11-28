#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import itertools

from pyramid.interfaces import IRequest

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.model import CourseCalendar

from nti.contenttypes.calendar.interfaces import ICalendarEventProvider

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_instructed_courses

from nti.dataserver.interfaces import IUser

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


@component.adapter(IUser)
@interface.implementer(ICalendarEventProvider)
class CourseCalendarEventProvider(object):

    def __init__(self, user):
        self.user = user

    def iter_events(self):
        res = []
        for enrollment in itertools.chain(get_enrollments(self.user),
                                          get_instructed_courses(self.user)) or ():
            course = ICourseInstance(enrollment, None)
            calendar = ICourseCalendar(course, None)
            if calendar is not None:
                res.extend([x for x in calendar.values()])
        return res
