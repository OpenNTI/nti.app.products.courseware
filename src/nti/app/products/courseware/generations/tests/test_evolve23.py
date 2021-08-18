#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from datetime import timedelta

from datetime import datetime

from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import has_key
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import not_

from zope.annotation import IAnnotations

from nti.app.products.courseware.calendar.attendance import CourseCalendarEventAttendanceContainer
from nti.app.products.courseware.calendar.attendance import CourseCalendarEventAttendanceContainerFactory
from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEventAttendanceContainer

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.generations import evolve23

from nti.app.products.courseware.generations.evolve23 import EVENT_ATTENDANCE

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.calendar.attendance import CalendarEventAttendanceContainerFactory
from nti.contenttypes.calendar.attendance import UserCalendarEventAttendance

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import StringPrincipal

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.testing.matchers import verifiably_provides


class TestEvolve23(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_no_attendance_storage(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            event_id = self.add_event().id

        self._callFUT()

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            calendar = self.get_course_calendar()
            event = calendar.retrieve_event(event_id)
            event_annotations = IAnnotations(event)

            assert_that(event_annotations, not_(has_key(EVENT_ATTENDANCE)))

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_no_attendance_records(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            event = self.add_event()
            event_id = event.id

            container = CalendarEventAttendanceContainerFactory(event)
            assert_that(container, not_(verifiably_provides(ICourseCalendarEventAttendanceContainer)))

        self._callFUT()

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            calendar = self.get_course_calendar()
            event = calendar.retrieve_event(event_id)
            event_annotations = IAnnotations(event)

            assert_that(event_annotations, has_key(EVENT_ATTENDANCE))

            container = event_annotations[EVENT_ATTENDANCE]
            assert_that(container, is_(CourseCalendarEventAttendanceContainer))
            assert_that(container, has_length(0))

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_no_migration_necessary(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            event = self.add_event()
            event_id = event.id

            original_container = CourseCalendarEventAttendanceContainerFactory(event)

        self._callFUT()

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            calendar = self.get_course_calendar()
            event = calendar.retrieve_event(event_id)
            event_annotations = IAnnotations(event)

            assert_that(event_annotations, has_key(EVENT_ATTENDANCE))

            container = event_annotations[EVENT_ATTENDANCE]
            assert_that(container, is_(original_container))
            assert_that(container, is_(CourseCalendarEventAttendanceContainer))
            assert_that(container, has_length(0))

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_attendance_records(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            event = self.add_event()
            event_id = event.id

            original_container = CalendarEventAttendanceContainerFactory(event)
            assert_that(original_container, not_(verifiably_provides(ICourseCalendarEventAttendanceContainer)))

            attendance = UserCalendarEventAttendance()
            attendance.creator = 'test_instructor_one'
            attendance.registrationTime = datetime.utcnow()
            original_container.add_attendance(StringPrincipal('test_student_one'), attendance)

            assert_that(attendance.createdTime, not_(0))
            assert_that(attendance.lastModified, not_(0))
            attendance.lastModified = attendance.registrationTime + timedelta(seconds=1)

        self._callFUT()

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            calendar = self.get_course_calendar()
            event = calendar.retrieve_event(event_id)
            event_annotations = IAnnotations(event)

            assert_that(event_annotations, has_key(EVENT_ATTENDANCE))

            container = event_annotations[EVENT_ATTENDANCE]
            assert_that(container, is_(CourseCalendarEventAttendanceContainer))
            assert_that(container, has_properties(
                __parent__=event,
                __name__=EVENT_ATTENDANCE,
                createdTime=original_container.createdTime,
                lastModified=original_container.lastModified))
            assert_that(container, has_length(1))

            attendance_record = tuple(container.values())[0]
            assert_that(attendance_record, has_property('Username', 'test_student_one'))
            assert_that(attendance_record, has_property('registrationTime', attendance.registrationTime))
            assert_that(attendance_record, has_property('createdTime', attendance.createdTime))
            assert_that(attendance_record, has_property('lastModified', attendance.lastModified))
            assert_that(attendance_record, has_property('creator', attendance.creator))
            assert_that(attendance_record, has_property('__parent__', container))
            assert_that(attendance_record, has_property('__name__', attendance.__name__))

    def add_event(self):
        calendar = self.get_course_calendar()
        event = CourseCalendarEvent(title=u'mince')
        calendar.store_event(event)

        return event

    def _callFUT(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            calendar = self.get_course_calendar()

            evolve23._process_calendar(calendar)

    def get_course_calendar(self):
        return ICourseCalendar(self.get_course())

    def get_course(self):
        entry = find_object_with_ntiid(self.entry_ntiid)
        return ICourseInstance(entry)
