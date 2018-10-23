#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import same_instance

from zope.annotation.interfaces import IAnnotations

from zope.container.interfaces import InvalidItemType

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.model import CourseCalendar
from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.contenttypes.calendar.model import CalendarEvent

from nti.contenttypes.courses.courses import CourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestAdapters(ApplicationLayerTest):

    @WithMockDSTrans
    def test_calendar(self):
        course = CourseInstance()

        connection = mock_dataserver.current_transaction
        connection.add(course)
        calendar = ICourseCalendar(course, None)
        assert_that(calendar, is_not(none()))
        assert_that(calendar.__parent__, same_instance(course))

        assert_that(calendar, validly_provides(ICourseCalendar))
        assert_that(calendar, verifiably_provides(ICourseCalendar))
        
        event = CourseCalendarEvent(title=u'gogo')
        calendar.store_event(event)

        assert_that(calendar, has_length(1))
        assert_that(event.ntiid, is_in(calendar))
        assert_that(list(calendar), has_length(1))

        assert_that(calendar.retrieve_event(event.ntiid), same_instance(event))
        assert_that(event.__parent__, same_instance(calendar))

        calendar.remove_event(event)
        assert_that(calendar, has_length(0))
        assert_that(event.__parent__, is_(None))

        annotations = IAnnotations(course)
        assert_that(annotations['CourseCalendar'], same_instance(calendar))

        # bad calendar event type
        event = CalendarEvent(title=u'abc')
        assert_that(calling(calendar.store_event).with_args(event), raises(InvalidItemType))
