#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.dataserver.users import User

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCourseAdminViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_views(self):
        all_entries_url = '/dataserver2/CourseAdmin/AllCatalogEntries'
        res = self.testapp.get(all_entries_url, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(8)))

        student = u"ichigo"
        with mock_dataserver.mock_db_trans(self.ds):
            User.create_user(username=student)

        enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
        data = {'username': student,
                'ntiid': self.course_ntiid, 
                'scope': 'ForCredit'}
        res = self.testapp.post_json(enroll_url, data, status=201)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courseware.courseinstanceenrollment',
                                'Username', 'ichigo',
                                'RealEnrollmentStatus', 'ForCredit'))

        enrollments_url = '/dataserver2/CourseAdmin/UserCourseEnrollments'
        params = {'username': student}
        res = self.testapp.get(enrollments_url, params, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(1)))

        drop_url = '/dataserver2/CourseAdmin/UserCourseDrop'
        data = {'username': student, 'ntiid': self.course_ntiid}
        self.testapp.post_json(drop_url, data, status=204)

        res = self.testapp.get(enrollments_url, params, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(0)))

        # enroll again
        data = {'username': student,
                'ntiid': self.course_ntiid, 
                'scope': 'ForCredit'}
        res = self.testapp.post_json(enroll_url, data, status=201)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courseware.courseinstanceenrollment',
                                'Username', 'ichigo',
                                'RealEnrollmentStatus', 'ForCredit'))

        drop_all_enrolls_url = '/dataserver2/CourseAdmin/DropAllCourseEnrollments'
        data = {'ntiid': self.course_ntiid}
        res = self.testapp.post_json(drop_all_enrolls_url, data, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(1)))

        res = self.testapp.get(enrollments_url, params, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(0)))
