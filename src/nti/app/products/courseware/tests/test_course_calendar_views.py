#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ
from datetime import datetime
from datetime import timedelta

from hamcrest import contains
from hamcrest import is_
from hamcrest import not_
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import has_properties
from hamcrest import same_instance
from hamcrest import contains_inanyorder

from zope.component.hooks import getSite

from zope.annotation.interfaces import IAnnotations

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.datetime import datetime_from_string

from nti.externalization.externalization.standard_fields import datetime_to_string


class TestCourseCalendarViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice'

    course_ntiid2 = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=(u'test_student',
                                                      u'admin001@nextthought.com',
                                                      u'site_user001',
                                                      u'editor_user001'))
    def test_course_calendar_views(self):
        admin_env = self._make_extra_environ('admin001@nextthought.com')
        site_admin_env = self._make_extra_environ('site_user001')
        editor_env = self._make_extra_environ('editor_user001')
        instructor_env = self._make_extra_environ('harp4162')
        student_env = self._make_extra_environ('test_student')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            # pylint: disable=too-many-function-args
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))

            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, 'site_user001')

            enroll_mgr = ICourseEnrollmentManager(course)
            enroll_mgr.enroll(User.get_user('test_student'))

            course_srm = IPrincipalRoleManager(course)
            course_srm.assignRoleToPrincipal(RID_CONTENT_EDITOR, 'editor_user001')

        # read calendar
        calendar_url = self.course_url + "/CourseCalendar"
        result = self.testapp.get(calendar_url + '/@@contents', status=200, extra_environ=admin_env).json_body
        assert_that(result, has_entries({'Items': has_length(0)}))

        result = self.testapp.get(calendar_url, params={'raw': True}, status=200, extra_environ=admin_env).json_body
        assert_that(result, has_entries({'title': 'Law and Justice',
                                         'description': None,
                                         'MimeType': 'application/vnd.nextthought.courseware.coursecalendar'}))

        res = self.testapp.get(calendar_url, status=200, extra_environ=site_admin_env)
        res = res.json_body
        assert_that(res, has_entry('CatalogEntry', not_none()))
        self.testapp.get(calendar_url, status=200, extra_environ=editor_env)
        self.testapp.get(calendar_url, status=200, extra_environ=student_env)

        # update calendar
        result = self.testapp.put_json(calendar_url, params={'title': 'calen', 'description': 'this'}, status=200, extra_environ=admin_env).json_body
        assert_that(result, has_entries({'title': 'calen',
                                         'description': 'this',
                                         'MimeType': 'application/vnd.nextthought.courseware.coursecalendar'}))

        self.testapp.put_json(calendar_url, params={'title': 'calen', 'description': 'this'}, status=200, extra_environ=site_admin_env)
        self.testapp.put_json(calendar_url, params={'title': 'calen', 'description': 'this'}, status=200, extra_environ=editor_env)
        self.testapp.put_json(calendar_url, params={'title': 'calen', 'description': 'this'}, status=403, extra_environ=student_env)

        # add calendar event: admin/site-admin, should we allow editor etc?
        params = {
            "MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
            "title": "go to school",
            "description": "let us go",
            "icon": "/home/go",
            "location": "oklahoma",
            "start_time": "2018-09-20T09:00Z",
            "end_time": "2018-09-20T12:00Z"
        }
        res = self.testapp.post_json(calendar_url, params=params, status=201, extra_environ=admin_env).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "title": "go to school",
                                      "description": "let us go",
                                      "icon": "/home/go",
                                      "location": "oklahoma",
                                      "start_time": "2018-09-20T09:00:00Z",
                                      "end_time": "2018-09-20T12:00:00Z",
                                      "Last Modified": not_none(),
                                      'CatalogEntryNTIID': u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice',
                                      "NTIID": not_none()}))
        event_id = res['ID']
        event_oid = res['OID']
        event_url = '/dataserver2/Objects/%s' % event_oid

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))

            calendar = ICourseCalendar(course)
            assert_that(calendar.__parent__, same_instance(course))
            assert_that(calendar, has_length(1))
            event = calendar.retrieve_event(event_id)
            assert_that(event.__parent__, same_instance(calendar))
            assert_that(event, has_properties({'title': 'go to school',
                                               'description': 'let us go',
                                               'icon': '/home/go',
                                               'location': 'oklahoma',
                                               'start_time': not_none(),
                                               'end_time': not_none()}))

        event_oid2 = self.testapp.post_json(calendar_url, params=params, status=201, extra_environ=site_admin_env).json_body['OID']
        event_oid3 = self.testapp.post_json(calendar_url, params=params, status=201, extra_environ=editor_env).json_body['OID']
        self.testapp.post_json(calendar_url, params=params, status=403, extra_environ=student_env)

        # read calendar event
        res = self.testapp.get(event_url, status=200, extra_environ=admin_env).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "NTIID": event_oid}))

        self.testapp.get(event_url, status=200, extra_environ=site_admin_env)
        self.testapp.get(event_url, status=200, extra_environ=editor_env)
        self.testapp.get(event_url, status=200, extra_environ=student_env)

        # update calendar event
        params = {'title': 'okay'}
        res = self.testapp.put_json(event_url, params=params, status=200, extra_environ=admin_env).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "NTIID": event_oid,
                                      "title": "okay"}))

        self.testapp.put_json(event_url, params=params, status=200, extra_environ=site_admin_env)
        self.testapp.put_json(event_url, params=params, status=200, extra_environ=editor_env)
        self.testapp.put_json(event_url, params=params, status=403, extra_environ=student_env)

        # fetch non-empty calendar
        result = self.testapp.get(calendar_url + '/@@contents', status=200, extra_environ=admin_env).json_body
        assert_that(result, has_entries({'Items': has_length(3)}))

        # Calendar collection
        student_calendars_href = '/dataserver2/users/test_student/Calendars'
        calendars = self.testapp.get(student_calendars_href,
                                     extra_environ=student_env)
        calendars = calendars.json_body
        self.require_link_href_with_rel(calendars, 'events')
        assert_that(calendars['Items'], has_length(1))
        assert_that(calendars['Items'][0],
                    has_entry('CatalogEntry',
                              has_entry('NTIID',
                                        u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice')))

        instructor_calendars_href = '/dataserver2/users/harp4162/Calendars'
        calendars = self.testapp.get(instructor_calendars_href,
                                     extra_environ=instructor_env)
        calendars = calendars.json_body
        self.require_link_href_with_rel(calendars, 'events')
        assert_that(calendars['Items'], has_length(1))
        assert_that(calendars['Items'][0],
                    has_entry('CatalogEntry',
                              has_entry('NTIID',
                                        u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice')))

        # Editors have no calendars
        editor_calendars_href = '/dataserver2/users/editor_user001/Calendars'
        calendars = self.testapp.get(editor_calendars_href,
                                     extra_environ=editor_env)
        calendars = calendars.json_body
        assert_that(calendars['Items'], has_length(0))

        # Cannot fetch another user's calendars
        self.testapp.get(instructor_calendars_href,
                         extra_environ=student_env,
                         status=403)

        # delete calendar event: admin/site-admin
        self.testapp.delete(event_url, status=403, extra_environ=student_env)
        self.testapp.delete(event_url, status=204, extra_environ=admin_env)
        self.testapp.delete('/dataserver2/Objects/%s' % event_oid2, status=204, extra_environ=editor_env)
        self.testapp.delete('/dataserver2/Objects/%s' % event_oid3, status=204, extra_environ=site_admin_env)

        # verify deleted event
        result = self.testapp.get(calendar_url + '/@@contents', status=200, extra_environ=admin_env).json_body
        assert_that(result, has_entries({'Items': has_length(0)}))
        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(calendar, has_length(0))

    @WithSharedApplicationMockDS(testapp=True, users=(u'owner001',))
    def testUserCompositeCalendarView(self):
        owner_env = self._make_extra_environ(username=u'owner001')
        url = '/dataserver2/users/owner001/Calendars/@@events'

        result = self.testapp.get(url, status=200, extra_environ=owner_env).json_body
        assert_that(result, has_entries({'Total': 0, 'Items': has_length(0)}))

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = User.get_user('owner001')
            for course_ntiid, titles in ((self.course_ntiid,(u'c_one', u'c_two')),
                                         (self.course_ntiid2,(u'c_three',))):
                entry = find_object_with_ntiid(course_ntiid)
                course = ICourseInstance(entry)

                enrollment_manager = ICourseEnrollmentManager(course)
                enrollment_manager.enroll(user)

                calendar = ICourseCalendar(course)
                for title in titles:
                    calendar.store_event(CourseCalendarEvent(title=title))

        result = self.testapp.get(url, status=200, extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two', u'c_three'))

        result = self.testapp.get(url, params={'context_ntiids': self.course_ntiid}, status=200, extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two'))

        result = self.testapp.get(url, params={'context_ntiids': self.course_ntiid2}, status=200, extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_three'))

        # empty string should be ignore.
        result = self.testapp.get(url, params={'context_ntiids': ''}, status=200, extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two', u'c_three'))

        result = self.testapp.get(url, params={'context_ntiids': 'abc'}, status=200, extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that(result, has_length(0))

        result = self.testapp.get(url,
                                  params={'context_ntiids': [self.course_ntiid2, self.course_ntiid]},
                                  extra_environ=owner_env)
        result = result.json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two', u'c_three'))

        result = self.testapp.get(url,
                                  params={'context_ntiids': [self.course_ntiid2, self.course_ntiid], 'exclude_dynamic_events': 'true'},
                                  extra_environ=owner_env).json_body
        assert_that(result['Items'], has_length(3))

        result = self.testapp.get(url,
                                  params={'context_ntiids': [self.course_ntiid2, self.course_ntiid]},
                                  extra_environ=owner_env).json_body
        assert_that(len(result['Items']), greater_than(3))

        # Excluded
        result = self.testapp.get(url, params={'excluded_context_ntiids': ''}, extra_environ=owner_env)
        result = result.json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two', u'c_three'))

        result = self.testapp.get(url, params={'excluded_context_ntiids': self.course_ntiid}, extra_environ=owner_env)
        result = result.json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_three'))

        result = self.testapp.get(url, params={'excluded_context_ntiids': self.course_ntiid2}, extra_environ=owner_env)
        result = result.json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two'))

        result = self.testapp.get(url,
                                  params={'excluded_context_ntiids': [self.course_ntiid2, self.course_ntiid]},
                                  extra_environ=owner_env)
        result = result.json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that(result, has_length(0))


        # dooming post view
        # context ntiids.
        result = self.testapp.post_json(url,
                                        params={'context_ntiids': [self.course_ntiid2, self.course_ntiid]},
                                        extra_environ=owner_env).json_body
        assert_that(len(result['Items']), greater_than(3))
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that(result, has_length(3))

        # strip duplicated ntiids.
        result = self.testapp.post_json(url,
                                        params={'context_ntiids': [self.course_ntiid, self.course_ntiid]},
                                        extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two'))

        # exclude dynamic events
        url = '/dataserver2/users/owner001/Calendars/@@events?exclude_dynamic_events=true'
        result = self.testapp.post_json(url,
                                        params={'context_ntiids': [self.course_ntiid2, self.course_ntiid]},
                                        extra_environ=owner_env).json_body
        assert_that(result['Items'], has_length(3))

        # excluded ntiids
        result = self.testapp.post_json(url,
                                        params={'excluded_context_ntiids': [self.course_ntiid2]},
                                        extra_environ=owner_env).json_body
        result = [x for x in result['Items'] if x['Class'] == 'CourseCalendarEvent']
        assert_that([x['title'] for x in result], contains_inanyorder(u'c_one', u'c_two'))

        # context_ntiids or excluded_context_ntiids it not list or None.
        result = self.testapp.post_json(url, params={'context_ntiids': None}, extra_environ=owner_env).json_body
        assert_that(result['Items'], has_length(3))

        result = self.testapp.post_json(url, params={'context_ntiids': []}, extra_environ=owner_env).json_body
        assert_that(result['Items'], has_length(3))

        result = self.testapp.post_json(url, params={'excluded_context_ntiids': None}, extra_environ=owner_env).json_body
        assert_that(result['Items'], has_length(3))

        result = self.testapp.post_json(url, params={'context_ntiids': ''}, status=422, extra_environ=owner_env).json_body
        assert_that(result['message'], is_('context_ntiids should be an array of ntiids or empty.'))

        result = self.testapp.post_json(url, params={'excluded_context_ntiids': 'a'}, status=422, extra_environ=owner_env).json_body
        assert_that(result['message'], is_('excluded_context_ntiids should be an array of ntiids or empty.'))


class TestCalendarEventAttendanceViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice'

    course_ntiid2 = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=(u'test_student',
                                                      u'test_student2',
                                                      u'admin001@nextthought.com',
                                                      u'site_user001',
                                                      u'editor_user001'))
    def test_record_calendar_event_attendance(self):
        admin_env = self._make_extra_environ('admin001@nextthought.com')
        site_admin_env = self._make_extra_environ('site_user001')
        editor_env = self._make_extra_environ('editor_user001')
        instructor_env = self._make_extra_environ('harp4162')
        student_env = self._make_extra_environ('test_student')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            # pylint: disable=too-many-function-args
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))

            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, 'site_user001')

            enroll_mgr = ICourseEnrollmentManager(course)
            enroll_mgr.enroll(User.get_user('test_student'))

            course_srm = IPrincipalRoleManager(course)
            course_srm.assignRoleToPrincipal(RID_CONTENT_EDITOR, 'editor_user001')

        # add calendar event: admin/site-admin, should we allow editor etc?
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
        res = self.testapp.post_json(calendar_url, params=params, status=201, extra_environ=admin_env).json_body

        attendance_url = self.require_link_href_with_rel(res, 'record-attendance')

        def record_attendance(env, username, **kwargs):
            kwargs['extra_environ'] = env
            record_attendance_url = "%s?username=%s" % (attendance_url, username)
            return self.testapp.post_json(record_attendance_url, **kwargs)

        # Only admins and instructors can record
        record_attendance(student_env, 'test_student', status=403)
        record_attendance(editor_env, 'test_student', status=403)

        res = record_attendance(instructor_env,
                                'test_student',
                                status=201).json_body
        assert_that(res, has_entries({
            'registrationTime': not_none(),
            'Creator': 'harp4162',
            'User': has_entries(Username='test_student')
        }))
        user_attendance_url = res['href']

        # Verify addition
        res = self.testapp.get(attendance_url, extra_environ=instructor_env).json_body
        assert_that(res['ItemCount'], is_(1))

        # No user
        res = record_attendance(instructor_env, 'not_a_user', status=422)
        assert_that(res.json_body['code'], is_('UserNotFound'))

        # User isn't enrolled
        res = record_attendance(instructor_env, 'test_student2', status=422)
        assert_that(res.json_body['code'], is_('InvalidAttendee'))

        # Recording attendance for the same student is a conflict
        record_attendance(instructor_env, 'test_student', status=409)
        self.testapp.delete(user_attendance_url, extra_environ=instructor_env)

        # Admins and site admins can also record, edit and delete
        def check_edit(user_env):
            # Record
            res = record_attendance(user_env, 'test_student').json_body

            edit_url = self.require_link_href_with_rel(res, 'edit')
            delete_url = self.require_link_href_with_rel(res, 'delete')
            attendance_href = res['href']

            # Edit
            new_time = (datetime.utcnow().replace(microsecond=0)
                        + timedelta(seconds=1))
            assert_that(datetime_from_string(res['registrationTime']), not_none())
            assert_that(datetime_from_string(res['registrationTime']), not_(new_time))
            new_time_str = datetime_to_string(new_time)
            updated_attendance = {'registrationTime': new_time_str}

            res = self.testapp.put_json(edit_url, updated_attendance, extra_environ=user_env).json_body
            assert_that(datetime_from_string(res['registrationTime']), is_(new_time))

            res = self.testapp.get(attendance_href, extra_environ=user_env).json_body
            assert_that(datetime_from_string(res['registrationTime']), is_(new_time))

            #   verify links available when fetched directly
            self.require_link_href_with_rel(res, 'edit')
            self.require_link_href_with_rel(res, 'delete')

            # Delete
            self.testapp.delete(delete_url, extra_environ=user_env)

        check_edit(admin_env)
        check_edit(site_admin_env)
        check_edit(instructor_env)

    @WithSharedApplicationMockDS(testapp=True, users=(u'test_student1',
                                                      u'test_student2',
                                                      u'test_student3',
                                                      u'admin001@nextthought.com',
                                                      u'admin002@nextthought.com',
                                                      u'site_user001',
                                                      u'editor_user001'))
    def test_get_calendar_event_attendance(self):
        admin_env = self._make_extra_environ('admin001@nextthought.com')
        admin_env2 = self._make_extra_environ('admin002@nextthought.com')
        site_admin_env = self._make_extra_environ('site_user001')
        editor_env = self._make_extra_environ('editor_user001')
        instructor_env = self._make_extra_environ('harp4162')
        student_env = self._make_extra_environ('test_student1')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            # pylint: disable=too-many-function-args
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))

            student1 = User.get_user('test_student1')
            student2 = User.get_user('test_student2')
            student3 = User.get_user('test_student3')

            enroll_mgr = ICourseEnrollmentManager(course)
            enroll_mgr.enroll(student1)
            enroll_mgr.enroll(student2)
            enroll_mgr.enroll(student3)

            IFriendlyNamed(student1).alias = u'bob'
            IFriendlyNamed(student2).alias = u'andy'
            IFriendlyNamed(student3).alias = u'chad'

            IFriendlyNamed(student1).realname = u'c clarence'
            IFriendlyNamed(student2).realname = u'andrew brown'
            IFriendlyNamed(student3).realname = u'b adams'

            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, 'site_user001')

            course_srm = IPrincipalRoleManager(course)
            course_srm.assignRoleToPrincipal(RID_CONTENT_EDITOR, 'editor_user001')

        # add calendar event: admin/site-admin, should we allow editor etc?
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
        res = self.testapp.post_json(calendar_url, params=params, status=201, extra_environ=instructor_env).json_body

        list_attendance_url = self.require_link_href_with_rel(res, 'list-attendance')
        record_attendance_url = self.require_link_href_with_rel(res, 'record-attendance')

        def record_attendance(env, username, **kwargs):
            kwargs['extra_environ'] = env
            post_attendance_url = "%s?username=%s" % (record_attendance_url, username)
            return self.testapp.post_json(post_attendance_url, **kwargs)

        record_attendance(admin_env, 'test_student1')
        record_attendance(instructor_env, 'test_student2')
        record_attendance(admin_env2, 'test_student3')

        # Only instructors and admins can see attendance
        self.testapp.get(list_attendance_url, status=403, extra_environ=student_env)
        self.testapp.get(list_attendance_url, status=403, extra_environ=editor_env)
        self.testapp.get(list_attendance_url, extra_environ=instructor_env)
        self.testapp.get(list_attendance_url, extra_environ=site_admin_env)
        self.testapp.get(list_attendance_url, extra_environ=admin_env)

        def assert_order(params, expected):
            res = self.testapp.get(list_attendance_url,
                                   params=params,
                                   extra_environ=instructor_env).json_body
            assert_that(res['ItemCount'], is_(len(expected)))
            user_attendance = [attendance['User']['Username']
                               for attendance in res['Items']]
            assert_that(user_attendance, contains(*expected))

        assert_order({},
                     ('test_student1', 'test_student2', 'test_student3'))
        assert_order({'sortOn': 'registrationTime'},
                     ('test_student1', 'test_student2', 'test_student3'))
        assert_order({'sortOn': 'registrationTime', 'sortOrder': 'invalid'},
                     ('test_student1', 'test_student2', 'test_student3'))
        assert_order({'sortOn': 'registrationTime', 'sortOrder': 'ascending'},
                     ('test_student1', 'test_student2', 'test_student3'))
        assert_order({'sortOn': 'alias', 'sortOrder': 'ascending'},
                     ('test_student2', 'test_student1', 'test_student3'))
        assert_order({'sortOn': 'realname', 'sortOrder': 'ascending'},
                     ('test_student2', 'test_student3', 'test_student1'))
        assert_order({'sortOn': 'username', 'sortOrder': 'descending'},
                     ('test_student3', 'test_student2', 'test_student1'))
        assert_order({'sortOn': 'lastname', 'sortOrder': 'ascending'},
                     ('test_student3', 'test_student2', 'test_student1'))
        assert_order({'sortOn': 'creator', 'sortOrder': 'ascending'},
                     ('test_student1', 'test_student3', 'test_student2'))

        assert_order({'batchStart': '1', 'batchSize': '1'},
                     ('test_student2',))

        # student1.alias is 'chad', student3 realname is 'c clarence'
        assert_order({'search': 'c',},
                     ('test_student1','test_student3'))
        # student2.realname is 'andrew brown'
        assert_order({'search': 'andrew'},
                     ('test_student2',))
        # matches all usernames
        assert_order({'search': 'student'},
                     ('test_student1', 'test_student2', 'test_student3'))
        # matches single username
        assert_order({'search': 'student3'},
                     ('test_student3',))

