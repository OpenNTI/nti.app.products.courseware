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

    def _recipients(self):
        course = ICourseInstance(self.context, None)
        if course is None:
            return ()

        enrollments = ICourseEnrollments(course, None)
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
