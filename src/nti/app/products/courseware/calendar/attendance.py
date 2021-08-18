#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.annotation import factory as an_factory

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.calendar.attendance import DefaultEventAttendanceManager

from nti.app.contenttypes.calendar.interfaces import ICalendarEventAttendanceManager

from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEventAttendanceContainer

from nti.contenttypes.calendar.attendance import CalendarEventAttendanceContainer

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseInstance


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICalendarEventAttendanceManager)
class CourseCalendarEventAttendanceManager(DefaultEventAttendanceManager):

    @Lazy
    def attendee_search_predicate(self):
        course = ICourseInstance(self.context)
        enrollments = ICourseEnrollments(course, None)

        if enrollments:
            return lambda user: enrollments.is_principal_enrolled(user)

        return lambda user: False


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICourseCalendarEventAttendanceContainer)
class CourseCalendarEventAttendanceContainer(CalendarEventAttendanceContainer):
    pass


CourseCalendarEventAttendanceContainerFactory = \
    an_factory(CourseCalendarEventAttendanceContainer, u'EventAttendance')
