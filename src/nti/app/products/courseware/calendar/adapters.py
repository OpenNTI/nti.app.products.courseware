#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import gevent

from pyramid.interfaces import IRequest

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware.adapters import get_valid_course_context

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarDynamicEventProvider
from nti.app.products.courseware.calendar.interfaces import IEnrolledCourseCalendarDynamicEventProvider

from nti.app.products.courseware.calendar.model import CourseCalendar

from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.interfaces import IHierarchicalContextProvider

from nti.contenttypes.calendar.interfaces import IAdminCalendarProvider
from nti.contenttypes.calendar.interfaces import ICalendarContextNTIIDAdapter
from nti.contenttypes.calendar.interfaces import ICalendarDynamicEventProvider
from nti.contenttypes.calendar.interfaces import ICalendarEvent
from nti.contenttypes.calendar.interfaces import ICalendarEventAttendanceContainer
from nti.contenttypes.calendar.interfaces import ICalendarEventProvider
from nti.contenttypes.calendar.interfaces import ICalendarProvider
from nti.contenttypes.calendar.interfaces import IUserCalendarEventAttendance

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_instructed_courses

from nti.dataserver.authorization import ACT_UPDATE

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


def _get_include_filter_lambda(filter_str):
    filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
    def check_entry_filter(entry):
        return filter_utility.include_entry(entry, filter_str)
    return check_entry_filter


def include_course_filter(course, entry_ntiids=None, excluded_entry_ntiids=None, include_filter_lambda=None):
    entry = ICourseCatalogEntry(course, None)
    return  entry is not None \
        and (not entry_ntiids or entry.ntiid in entry_ntiids) \
        and (not excluded_entry_ntiids or entry.ntiid not in excluded_entry_ntiids) \
        and (not include_filter_lambda or include_filter_lambda(entry))


def _iter_enrolled_courses_for_user(user, entry_ntiids=None, excluded_entry_ntiids=None, include_filter=None):
    include_filter_lambda = None
    if include_filter:
        include_filter_lambda = _get_include_filter_lambda(include_filter)
    for enrollment in get_enrollments(user) or ():
        course = ICourseInstance(enrollment, None)
        entry = ICourseCatalogEntry(course, None)
        is_preview_course = entry is not None and entry.Preview
        if      course is not None \
            and not is_preview_course \
            and include_course_filter(course,
                                      entry_ntiids=entry_ntiids,
                                      excluded_entry_ntiids=excluded_entry_ntiids,
                                      include_filter_lambda=include_filter_lambda):
            yield course


def _iter_admin_courses_for_user(user, entry_ntiids=None, excluded_entry_ntiids=None, include_filter=None):
    include_filter_lambda = None
    if include_filter:
        include_filter_lambda = _get_include_filter_lambda(include_filter)
    for instructed_course in get_instructed_courses(user) or ():
        course = ICourseInstance(instructed_course, None)
        if      course is not None \
            and include_course_filter(course,
                                      entry_ntiids=entry_ntiids,
                                      excluded_entry_ntiids=excluded_entry_ntiids,
                                      include_filter_lambda=include_filter_lambda):
            yield course


def _iter_all_courses_for_user(user, *args, **kwargs):
    for course in _iter_admin_courses_for_user(user, *args, **kwargs):
        yield course
    for course in _iter_enrolled_courses_for_user(user, *args, **kwargs):
        yield course


@component.adapter(IUser)
@interface.implementer(ICalendarProvider)
class CourseCalendarProvider(object):

    def __init__(self, user):
        self.user = user

    def _include_calendar(self, calendar):
        return True

    def iter_calendars(self, context_ntiids=None, excluded_context_ntiids=None, include_filter=None):
        for course in self._courses(self.user, context_ntiids, excluded_context_ntiids, include_filter):
            calendar = ICourseCalendar(course, None)
            if calendar is not None and self._include_calendar(calendar):
                yield calendar

    def _courses(self, user, entry_ntiids=None, excluded_entry_ntiids=None, include_filter=None):
        return _iter_all_courses_for_user(user, entry_ntiids, excluded_entry_ntiids, include_filter)


@component.adapter(IUser)
@interface.implementer(IAdminCalendarProvider)
class CourseAdminCalendarProvider(CourseCalendarProvider):
    """
    Return the course calenders this user can update.
    """

    def _include_calendar(self, calendar):
        return has_permission(ACT_UPDATE, calendar)


@component.adapter(IUser)
@interface.implementer(ICalendarEventProvider)
class AdminCourseCalendarEventProvider(object):
    """
    A calendar event provider that for a user's administered courses, fetches all
    persistent and dynamic events.
    """

    def __init__(self, user):
        self.user = user

    def _get_events(self, course, accum, exclude_dynamic=False):
        calendar = ICourseCalendar(course, None)
        if calendar is not None:
            accum.extend([x for x in calendar.values()])
        # add course dynamic events.
        if not exclude_dynamic:
            providers = component.subscribers((self.user, course),
                                              ICourseCalendarDynamicEventProvider)
            for x in providers or ():
                accum.extend(x.iter_events())

    def iter_events(self, context_ntiids=None, excluded_context_ntiids=None, exclude_dynamic=False, **kwargs):
        res = []
        for course in self._courses(self.user, context_ntiids, excluded_context_ntiids):
            self._get_events(course, res, exclude_dynamic)
            gevent.sleep()
        return res

    def _courses(self, user, entry_ntiids=None, excluded_entry_ntiids=None):
        """
        Gather the courses we want to gather events for. Include any courses
        that are in the inclusive `entry_ntiids` param and exclude any in the
        `excluded_entry_ntiids` param.
        """
        return _iter_admin_courses_for_user(user, entry_ntiids, excluded_entry_ntiids)


@component.adapter(IUser)
@interface.implementer(ICalendarEventProvider)
class EnrolledCourseCalendarEventProvider(AdminCourseCalendarEventProvider):
    """
    A calendar event provider that for a user's enrolled courses, fetches all
    parent class events (persistent and dynamic), as well as the dynamic
    enrolled course events (e.g. assignments).
    """

    def _get_events(self, course, accum, exclude_dynamic=False):
        super(EnrolledCourseCalendarEventProvider, self)._get_events(course,
                                                                     accum,
                                                                     exclude_dynamic)
        # add course dynamic events.
        if not exclude_dynamic:
            providers = component.subscribers((self.user, course),
                                              IEnrolledCourseCalendarDynamicEventProvider)
            for x in providers or ():
                accum.extend(x.iter_events())

    def _courses(self, user, entry_ntiids=None, excluded_entry_ntiids=None):
        """
        Gather the courses we want to gather events for. Include any courses
        that are in the inclusive `entry_ntiids` param and exclude any in the
        `excluded_entry_ntiids` param.
        """
        return _iter_enrolled_courses_for_user(user, entry_ntiids, excluded_entry_ntiids)


# FIXME Is this used or needed? I dont think so.
@component.adapter(IUser)
@interface.implementer(ICalendarDynamicEventProvider)
class CourseCalendarDynamicEventProvider(object):

    def __init__(self, user):
        self.user = user

    def iter_events(self):
        res = []
        for course in _iter_all_courses_for_user(self.user):
            providers = component.subscribers((self.user, course),
                                              ICourseCalendarDynamicEventProvider)

            for x in providers or ():
                res.extend(x.iter_events())
            gevent.sleep()
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


@component.adapter(ICalendarEventAttendanceContainer)
@interface.implementer(ICourseInstance)
def attendance_container_to_course(container):
    return find_interface(container, ICourseInstance, strict=False)


@component.adapter(ICalendarEventAttendanceContainer)
@interface.implementer(ICalendarEvent)
def attendance_container_to_event(container):
    return find_interface(container, ICalendarEvent, strict=False)


@component.adapter(IUserCalendarEventAttendance)
@interface.implementer(ICalendarEventAttendanceContainer)
def attendance_to_container(container):
    return find_interface(container, ICalendarEventAttendanceContainer, strict=False)


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


@component.adapter(ICourseCalendar, IUser)
@interface.implementer(IHierarchicalContextProvider)
class UserCourseCalendarHierarchyPathProvider(object):

    def __init__(self, obj, user):
        self.obj = obj
        self.user = user

    def get_context_paths(self, context=None):
        course = ICourseInstance(self.obj, None)
        courses = get_valid_course_context(course)
        return [(courses[0], self.obj)] if courses else ()


@component.adapter(ICourseCalendarEvent, IUser)
@interface.implementer(IHierarchicalContextProvider)
class UserCourseCalendarEventHierarchyPathProvider(object):

    def __init__(self, obj, user):
        self.obj = obj
        self.user = user

    def get_context_paths(self, context=None):
        calendar = ICourseCalendar(self.obj, None)
        course = ICourseInstance(calendar, None)
        courses = get_valid_course_context(course)
        return [(courses[0], calendar, self.obj)] if courses else ()
