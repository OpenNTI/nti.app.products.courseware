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

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.contenttypes.calendar.interfaces import ICalendarEventNotifier
from nti.contenttypes.calendar.interfaces import ICalendarEventNotificationValidator

from nti.contenttypes.calendar.processing import generate_score

from nti.app.contenttypes.calendar.notification import CalendarEventNotifier


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICalendarEventNotifier)
class CourseCalendarEventNotifier(CalendarEventNotifier):

    def _subject(self):
        return 'Upcoming course calendar event'

    @Lazy
    def course(self):
        return ICourseInstance(self.context, None)

    def _calendar_context(self):
        return getattr(self.course, 'title', u'Course')

    def _recipients(self):
        if self.course is None:
            return ()

        enrollments = ICourseEnrollments(self.course, None)
        if enrollments is None:
            return ()

        users = [User.get_user(x) for x in enrollments.iter_principals()]
        return [x for x in users if IUser.providedBy(x)]


@component.adapter(ICourseCalendarEvent)
@interface.implementer(ICalendarEventNotificationValidator)
class CourseCalendarEventNotificationValidator(object):

    def __init__(self, context):
        self.context = context

    def validate(self, original_score=None, *args, **kwargs):
        curr_score = generate_score(self.context)
        if curr_score != original_score:
            return False
        return True
