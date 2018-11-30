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
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.app.products.courseware.calendar.model import CourseCalendar

from nti.contenttypes.calendar.interfaces import ICalendarProvider
from nti.contenttypes.calendar.interfaces import ICalendarEventProvider
from nti.contenttypes.calendar.interfaces import ICalendarContextNTIIDAdapter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_instructed_courses

from nti.dataserver.interfaces import IUser

from nti.traversal.traversal import find_interface

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
def _CourseCalendarPathAdapter(context, unused_request):
    return _CourseCalendarFactory(context)


@component.adapter(IUser)
@interface.implementer(ICalendarProvider)
class CourseCalendarProvider(object):

    def __init__(self, user):
        self.user = user

    def iter_calendars(self):
        res = []
        for enrollment in itertools.chain(get_enrollments(self.user),
                                          get_instructed_courses(self.user)) or ():
            course = ICourseInstance(enrollment, None)
            calendar = ICourseCalendar(course, None)
            if calendar is not None:
                res.append(calendar)
        return res


@component.adapter(IUser)
@interface.implementer(ICalendarEventProvider)
class CourseCalendarEventProvider(object):

    def __init__(self, user):
        self.user = user

    def iter_events(self, context_ntiids=None, **kwargs):
        res = []
        for course in self._courses(self.user, context_ntiids):
            calendar = ICourseCalendar(course, None)
            if calendar is not None:
                res.extend([x for x in calendar.values()])
        return res

    def _courses(self, user, entry_ntiids=None):
        res = []
        for enrollment in itertools.chain(get_enrollments(user),
                                          get_instructed_courses(user)) or ():
            course = ICourseInstance(enrollment, None)
            entry = ICourseCatalogEntry(course, None)
            if entry is not None and (entry_ntiids is None or entry.ntiid in entry_ntiids):
                res.append(course)
        return res


@component.adapter(ICourseCalendar)
@interface.implementer(ICourseInstance)
def calendar_to_course(calendar):
    return find_interface(calendar, ICourseInstance, strict=False)


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICourseInstance)
def calendarevent_to_course(event):
    return find_interface(event, ICourseInstance, strict=False)


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICourseCalendar)
def calendarevent_to_calendar(event):
    return find_interface(event, ICourseCalendar, strict=False)


# calendar event catalog

class _NTIID(object):

    __slots__ = (b'contextNTIID',)

    def __init__(self, ntiid, default=None):
        self.contextNTIID = ntiid

    def __reduce__(self):
        raise TypeError()


@interface.implementer(ICalendarContextNTIIDAdapter)
@component.adapter(ICourseCalendarEvent)
def _course_calendar_event_to_ntiid(context):
    course = ICourseInstance(context, None)
    entry = ICourseCatalogEntry(course, None)
    return _NTIID(entry.ntiid) if entry is not None else None
