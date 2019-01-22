#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import fudge

from datetime import datetime

from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import is_
from hamcrest import contains

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.contenttypes.calendar.interfaces import ICalendarEventNotifier
from nti.contenttypes.calendar.interfaces import ICalendarEventNotificationValidator

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


class TestNotification(ApplicationLayerTest):

    @WithMockDSTrans
    def test_notification_validator(self):
        event = CourseCalendarEvent(title=u'abc', start_time=datetime.utcfromtimestamp(3600))
        validator = ICalendarEventNotificationValidator(event)
        assert_that(validator.validate(1800), is_(True))
        assert_that(validator.validate(1000), is_(False))
        assert_that(validator.validate(2000), is_(False))

    @WithMockDSTrans
    def test_notifier(self):
        event = CourseCalendarEvent(title=u'abc')
        notifier = ICalendarEventNotifier(event)
        assert_that(notifier._recipients(), has_length(0))

        course = CourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)
        calendar = ICourseCalendar(course)
        calendar.store_event(event)
        notifier = ICalendarEventNotifier(event)
        notifier._remaining = 25
        assert_that(notifier._recipients(), has_length(0))

        user = User.create_user(username=u'test001')
        enrollment_manager = ICourseEnrollmentManager(course)
        enrollment_manager.enroll(user)
        notifier = ICalendarEventNotifier(event)
        notifier._remaining = 25
        assert_that(notifier._recipients(), has_length(1))
        assert_that(notifier._recipients(), contains(user))
