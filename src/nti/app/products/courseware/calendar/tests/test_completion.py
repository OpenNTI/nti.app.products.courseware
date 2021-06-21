#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods
from datetime import datetime

from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entries
from hamcrest import assert_that

from ZODB.interfaces import IConnection

from zope import component

from zope.annotation import IAnnotations

from zope.security.interfaces import IPrincipal

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.calendar.attendance import UserCalendarEventAttendance

from nti.contenttypes.calendar.interfaces import ICalendarEventAttendanceContainer

from nti.contenttypes.calendar.model import CalendarEvent

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.progress import Progress

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid


class TestCompletionPolicy(ApplicationLayerTest):

    def test_externalization(self):
        event = CalendarEvent()
        course = ContentCourseInstance()
        policy = component.queryMultiAdapter((event, course), ICompletableItemCompletionPolicy)
        assert_that(policy, is_not(none()))
        assert_that(to_external_object(policy),
                    has_entries({
                        'Class': 'CalendarEventCompletionPolicy',
                        'offers_completion_certificate': False
                    }))

    def test_none_progress(self):
        event = CalendarEvent()
        course = ContentCourseInstance()
        policy = component.queryMultiAdapter((event, course), ICompletableItemCompletionPolicy)
        assert_that(policy, is_not(none()))

        assert_that(policy.is_complete(None), is_(none()))

    @WithMockDSTrans
    def test_no_progress(self):
        user = User.create_user(username='ccrunch')
        event = CalendarEvent()
        course = ContentCourseInstance()
        policy = component.queryMultiAdapter((event, course), ICompletableItemCompletionPolicy)
        assert_that(policy, is_not(none()))

        last_modified = datetime.utcnow()
        progress = Progress(NTIID=u'test_ntiid',
                            User=user,
                            Item=event,
                            CompletionContext=course,
                            LastModified=last_modified,
                            HasProgress=True)
        completed_item = policy.is_complete(progress)
        assert_that(completed_item, is_not(none()))
        assert_that(completed_item, has_properties(
            Item=event,
            Principal=user,
            CompletedDate=last_modified,
            Success=True,
        ))


class TestProgress(ApplicationLayerTest):

    @WithMockDSTrans
    def test_no_progress(self):
        user = User.create_user(username='ccrunch')
        event = CalendarEvent()
        course = ContentCourseInstance()
        progress = component.queryMultiAdapter((user, event, course), IProgress)
        assert_that(progress, is_(none()))

    @WithMockDSTrans
    def test_progress(self):
        user = User.create_user(username='ccrunch')
        event = CalendarEvent()
        IConnection(self.ds.root).add(event)
        container = ICalendarEventAttendanceContainer(event)
        attendance = UserCalendarEventAttendance(Username=user.username,
                                                 registrationTime=datetime.now())
        attendance.created = datetime.utcnow()
        container[IPrincipal(user).id] = attendance
        course = ContentCourseInstance()
        progress = component.queryMultiAdapter((user, event, course), IProgress)
        assert_that(progress, is_not(none()))
        assert_that(progress, has_properties(
            NTIID=is_(event.ntiid),
            LastModified=is_(attendance.created),
            User=is_(user),
            Item=is_(event),
            CompletionContext=is_(course),
            HasProgress=is_(True),
        ))


class TestCompletion(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'

    group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_required(self):
        self._test_completion(required=True)

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_optional(self):
        self._test_completion(required=False)

    def _test_completion(self, required=True):
        instructor_env = self._make_extra_environ('cs1323_instructor')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            # pylint: disable=too-many-function-args
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))
            container = ICompletionContextCompletionPolicyContainer(course)
            container.set_context_policy(CompletableItemAggregateCompletionPolicy())

            username = 'test_student1'
            self._create_and_enroll(course, username)

        res = self._create_event()

        record_attendance_url = self.require_link_href_with_rel(res, 'record-attendance')
        event_ntiid = res['NTIID']

        # Add event to lesson and publish it
        self.add_to_lesson_and_publish(event_ntiid)

        res = self.testapp.get(self.course_url).json_body

        # Make event required, if necessary
        if required:
            required_url = self.require_link_href_with_rel(res['CompletionPolicy'], 'Required')
            data = dict(ntiid=event_ntiid)
            self.testapp.put_json(required_url, data)

        self._check_completion(username, is_completed=False)

        # Record attendance for student
        data = dict(Username='test_student1')
        kwargs = dict(extra_environ=instructor_env)
        attendance = self.testapp.post_json(record_attendance_url, data, **kwargs).json_body

        self._check_completion(username, is_completed=required)

        # Remove attendance for student
        kwargs = dict(extra_environ=instructor_env)
        self.testapp.delete(attendance['href'], **kwargs)

        self._check_completion(username, is_completed=False)

        # remove calendar event
        self.testapp.delete('/dataserver2/NTIIDs/%s' % event_ntiid, status=204)

    def add_to_lesson_and_publish(self, event_ntiid):
        res = self.testapp.get('/dataserver2/Objects/%s' % self.group_ntiid).json_body
        assert_that(res.get('Items'), has_length(1))
        contents_link = self.require_link_href_with_rel(res, 'ordered-contents')

        data = {
            'MimeType': 'application/vnd.nextthought.nticalendareventref',
            'target': event_ntiid,
        }
        self.testapp.post_json(contents_link, data, status=201)

    def _check_completion(self, username, is_completed):
        res = self.testapp.get('/dataserver2/users/%s/Courses/EnrolledCourses/%s'
                               % (username, self.course_ntiid),
                               extra_environ=self._make_extra_environ(username)).json_body
        assert_that(res, has_entries(CourseProgress=is_not(none())))
        assert_that(res['CourseProgress'], has_entries(Completed=is_completed))

    def _create_event(self, **kwargs):
        calendar_url = self.course_url + "/CourseCalendar"
        params = {
            "MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
            "title": "go to school",
            "description": "let us go",
            "icon": "/home/go",
            "location": "oklahoma",
            "start_time": "2018-09-20T09:00Z",
            "end_time": "2018-09-20T12:00Z"
        }
        return  self.testapp.post_json(calendar_url,
                                       params=params,
                                       status=201,
                                       **kwargs).json_body

    def _create_and_enroll(self, course, username):
        student1 = self._create_user(username,
                                     external_value={
                                         "realname": u"%s Test" % username,
                                         "email": u"%s@student.edu" % username,
                                     })
        enroll_mgr = ICourseEnrollmentManager(course)
        enroll_mgr.enroll(student1)
