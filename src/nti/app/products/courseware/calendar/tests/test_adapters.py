#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import none
from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import same_instance
from hamcrest import has_items
from hamcrest import contains_inanyorder

from zope.annotation.interfaces import IAnnotations

from zope.container.interfaces import InvalidItemType

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.adapters import CourseCalendarEventProvider
from nti.app.products.courseware.calendar.adapters import _hierarchy_from_calendar_and_user
from nti.app.products.courseware.calendar.adapters import _hierarchy_from_calendar_event_and_user

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.contenttypes.calendar.model import CalendarEvent

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


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
        assert_that(event.id, is_in(calendar))
        assert_that(list(calendar), has_length(1))

        assert_that(calendar.retrieve_event(event.id), same_instance(event))
        assert_that(event.__parent__, same_instance(calendar))

        calendar.remove_event(event)
        assert_that(calendar, has_length(0))
        assert_that(event.__parent__, is_(None))

        annotations = IAnnotations(course)
        assert_that(annotations['CourseCalendar'], same_instance(calendar))

        # bad calendar event type
        event = CalendarEvent(title=u'abc')
        assert_that(calling(calendar.store_event).with_args(event), raises(InvalidItemType))

    @WithMockDSTrans
    @fudge.patch('nti.app.products.courseware.calendar.adapters.get_valid_course_context')
    def test_library_path(self, mock_valid_course_context):
        user = User.create_user(username=u'test001')
        course = CourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)

        calendar = ICourseCalendar(course, None)
        mock_valid_course_context.is_callable().with_args(course).returns((course,))
        res = _hierarchy_from_calendar_and_user(calendar, user)
        assert_that(res[0], contains(course, calendar))

        event = CourseCalendarEvent(title=u'gogo')
        mock_valid_course_context.is_callable().with_args(None).returns(())
        res = _hierarchy_from_calendar_event_and_user(event, user)
        assert_that(res, has_length(0))

        calendar.store_event(event)
        mock_valid_course_context.is_callable().with_args(course).returns((course,))
        res = _hierarchy_from_calendar_event_and_user(event, user)
        assert_that(res, has_length(1))
        assert_that(res[0], contains(course, calendar, event))


class TestCourseCalendarEventProvider(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    course_ntiid2 = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=(u'test001', u'creator001'))
    def testCourseCalendarEventProvider(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)

            creator = User.get_user(u'creator001')

            # no enrollment
            user = User.get_user(u'test001')
            provider = CourseCalendarEventProvider(user)
            assert_that(provider.iter_events(), has_length(0))

            # course has no events.
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
            assert_that(provider.iter_events(), has_length(0))

            event = CourseCalendarEvent(title=u'c_one')
            event.creator = creator
            ICourseCalendar(course).store_event(event)
            event = CourseCalendarEvent(title=u'c_two')
            event.creator = creator
            ICourseCalendar(course).store_event(event)
            assert_that(provider.iter_events(), has_length(2))
            assert_that([x.title for x in provider.iter_events()], contains_inanyorder('c_one', 'c_two'))

            # enroll another course.
            entry2 = find_object_with_ntiid(self.course_ntiid2)
            course2 = ICourseInstance(entry2)
            enrollment_manager2 = ICourseEnrollmentManager(course2)
            enrollment_manager2.enroll(user)
            event = CourseCalendarEvent(title=u'c_three')
            event.creator = creator
            ICourseCalendar(course2).store_event(event)

            assert_that([x.title for x in provider.iter_events()], has_items('c_one', 'c_two', 'c_three'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=None)], has_items('c_one', 'c_two', 'c_three'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=[entry.ntiid, entry2.ntiid])], has_items('c_one', 'c_two', 'c_three'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=[entry.ntiid])], has_items('c_one', 'c_two'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=[entry2.ntiid])], has_items('c_three'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=[])], has_items('c_one', 'c_two', 'c_three'))
            assert_that([x.title for x in provider.iter_events(context_ntiids=[ICourseCatalogEntry(course2.SubInstances['001']).ntiid])], has_length(0))
