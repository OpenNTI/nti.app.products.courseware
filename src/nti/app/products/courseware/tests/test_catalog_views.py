#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

import time

from datetime import datetime

from zope import component

from nti.app.products.courseware.views import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware.views import VIEW_COURSE_CATALOG_FAMILIES
from nti.app.products.courseware.views import VIEW_UPCOMING_COURSES
from nti.app.products.courseware.views import VIEW_ARCHIVED_COURSES
from nti.app.products.courseware.views import VIEW_CURRENT_COURSES

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestCatalogViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = b'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=False)
    def test_anonymously_available_courses_view(self):
        anonymous_instances_url = '/dataserver2/_AnonymouslyButNotPubliclyAvailableCourseInstances'

        # authed users also can't fetch this view
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('ichigo')

        unauthed_environ = self._make_extra_environ(username='ichigo')
        self.testapp.get(
                    anonymous_instances_url,
                    extra_environ=unauthed_environ,
                    status=403)

        # unauthed requests that have our special classifier are allowed
        extra_environ = self._make_extra_environ(username=None)
        result = self.testapp.get(
                    anonymous_instances_url,
                    extra_environ=extra_environ)
        result = result.json_body
        assert_that(result, has_entry('ItemCount', 1))

    def _create_and_enroll(self, username, section=None):
        with mock_dataserver.mock_db_trans():
            self._create_user( username )

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            user = User.get_user(username)
            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323' ]
            if section:
                course = course.SubInstances[section]
            manager = ICourseEnrollmentManager(course)
            manager.enroll(user, scope='ForCreditDegree')

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_catalog_families(self):
        parent_user = 'parent_user'
        section_user1 = 'section_user1'
        section_user2 = 'section_user2'
        self._create_and_enroll(parent_user)
        self._create_and_enroll(section_user1, section='010')
        self._create_and_enroll(section_user2, section='995')

        enroll_href = "/dataserver2/users/%s/Courses/EnrolledCourses"
        for user in (parent_user, section_user1, section_user2):
            environ = self._make_extra_environ(user)
            res = self.testapp.get(enroll_href % user, extra_environ=environ)
            res = res.json_body
            assert_that(res[ITEMS], has_length(1))
            record = res[ITEMS][0]
            entry_ntiid = record['CatalogEntryNTIID']
            assert_that(entry_ntiid, not_none())
            course_ext = record['CourseInstance']

            # Enrolled only have access to their entry, so nothing is returned.
            families_href = self.require_link_href_with_rel(course_ext,
															VIEW_COURSE_CATALOG_FAMILIES)
            families = self.testapp.get(families_href, extra_environ=environ)
            families = families.json_body
            assert_that(families[ITEM_COUNT], is_(1), user)
            # Now fetch access
            access_href = self.require_link_href_with_rel(course_ext,
														  VIEW_USER_COURSE_ACCESS)
            access = self.testapp.get(access_href, extra_environ=environ)
            access = access.json_body
            assert_that(access[CLASS], is_('CourseInstanceEnrollment'))


            # Admins
            entry = self.testapp.get( '/dataserver2/Objects/%s' % entry_ntiid )
            entry = entry.json_body

            # Admins have access to all parents/sections; so 4 are returned
            families_href = self.require_link_href_with_rel(entry,
															VIEW_COURSE_CATALOG_FAMILIES)
            families = self.testapp.get(families_href)
            families = families.json_body
            assert_that(families[ITEM_COUNT], is_(4))

            # Fetch administrative role
            access_href = self.require_link_href_with_rel(entry,
														  VIEW_USER_COURSE_ACCESS)
            access = self.testapp.get(access_href)
            access = access.json_body
            assert_that(access[CLASS], is_('CourseInstanceAdministrativeRole'))
            assert_that(access['RoleName'], is_('editor'))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_administered_paging(self):
        favorites_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AdministeredCourses/@@WindowedAdministered"

        notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
        notAfter = time.mktime(datetime(2015, 8, 25).timetuple())

        get_params = {"notBefore": notBefore, "notAfter": notAfter}

        res = self.testapp.get(favorites_path, get_params)

        assert_that(res.json_body, has_entry("ItemCount", 7))

        # If I give no parameters, then I should get everything
        res = self.testapp.get(favorites_path)
        assert_that(res.json_body, has_entry("ItemCount", 7))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_enrolled_paging(self):
        enroll_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses"
        get_enrolled_courses_path = enroll_path + "/@@WindowedEnrolled"

        notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
        notAfter = time.mktime(datetime(2015, 8, 25).timetuple())

        get_params = {"notBefore": notBefore, "notAfter": notAfter}

        res = self.testapp.get(get_enrolled_courses_path, get_params)
        assert_that(res.json_body, get_params, has_entry("Items", has_length(1)))

        self.testapp.post_json(enroll_path,
                         'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice',
                         status=201)
        self.testapp.post_json(enroll_path,
                         'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995',
                         status=201)

        res = self.testapp.get(enroll_path)
        assert_that(res.json_body, has_entry("Items", has_length(2)))

        res = self.testapp.get(get_enrolled_courses_path, get_params)
        assert_that(res.json_body, has_entry("ItemCount", 2))

        # If I give just notBefore, then I should get everything after that
        notBefore = time.mktime(datetime(2014, 8, 14).timetuple())
        get_params = {"notBefore": notBefore}

        res = self.testapp.get(get_enrolled_courses_path, get_params)
        assert_that(res.json_body, get_params, has_entry("ItemCount", 1))

        # Similar to notAfter
        notAfter = time.mktime(datetime(2014, 8, 25).timetuple())
        get_params = {"notAfter": notAfter}

        res = self.testapp.get(get_enrolled_courses_path, get_params)
        assert_that(res.json_body, get_params, has_entry("ItemCount", 1))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_all_paging(self):
        all_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses"
        res = self.testapp.get(all_path)

        assert_that(res.json_body, has_entry("Items", has_length(8)))

        all_paged_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@WindowedAllCourses"

        notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
        notAfter = time.mktime(datetime(2015, 8, 1).timetuple())

        get_params = {"notBefore": notBefore, "notAfter": notAfter}

        res = self.testapp.get(all_paged_path, get_params)
        assert_that(res.json_body, has_entry("ItemCount", 4))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_bad_page_request(self):
        enroll_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/@@WindowedEnrolled"

        get_params = {"notBefore": "Garbage"}

        # Test with not an integer
        self.testapp.get(
                    enroll_path,
                    get_params,
                    status=422)

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_upcoming_course_view(self):
        upcoming_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@" + VIEW_UPCOMING_COURSES
        
        res = self.testapp.get(upcoming_course_path, 
                               status=200)
        
        res = res.json_body
        assert_that(res, has_entry("ItemCount", 0))
        
    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_archived_course_view(self):
        archived_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@" + VIEW_ARCHIVED_COURSES
        
        res = self.testapp.get(archived_course_path, 
                               status=200)
        
        res = res.json_body
        assert_that(res, has_entry("ItemCount", 5))
    
    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_current_course_view(self):
        archived_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@" + VIEW_CURRENT_COURSES
        
        res = self.testapp.get(archived_course_path, 
                               status=200)
        
        res = res.json_body
        assert_that(res, has_entry("ItemCount", 3))
        