#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import contains_string
from hamcrest import is_
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

from zope import component

from zope.event import notify

from nti.app.products.courseware.views import VIEW_CURRENT_COURSES
from nti.app.products.courseware.views import VIEW_ARCHIVED_COURSES
from nti.app.products.courseware.views import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware.views import VIEW_COURSE_CATALOG_FAMILIES

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.coremetadata.interfaces import UserProcessedContextsEvent

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.users import User

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestCatalogViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=False)
    def test_anonymously_available_courses_view(self):
        anonymous_instances_url = '/dataserver2/_AnonymouslyButNotPubliclyAvailableCourseInstances'

        # authed users also can't fetch this view
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'ichigo')

        unauthed_environ = self._make_extra_environ(username='ichigo')
        self.testapp.get(anonymous_instances_url,
                         extra_environ=unauthed_environ,
                         status=403)

        # unauthed requests that have our special classifier are allowed
        extra_environ = self._make_extra_environ(username=None)
        result = self.testapp.get(anonymous_instances_url,
                                  extra_environ=extra_environ)
        result = result.json_body
        assert_that(result, has_entry('ItemCount', 1))

    def _create_and_enroll(self, username, section=None):
        with mock_dataserver.mock_db_trans():
            if not User.get_user(username):
                self._create_user(username)

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            user = User.get_user(username)
            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            if section:
                course = course.SubInstances[section]
            manager = ICourseEnrollmentManager(course)
            manager.enroll(user, scope='ForCreditDegree')

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_catalog_families(self):
        parent_user = u'parent_user'
        section_user1 = u'section_user1'
        section_user2 = u'section_user2'
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
            course_href = self.require_link_href_with_rel(record, 'CourseInstance')
            course_ext = self.testapp.get(course_href, extra_environ=environ).json_body

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
            assert_that(access['href'], contains_string('EnrolledCourses'))

            # Admins
            entry = self.testapp.get('/dataserver2/Objects/%s' % entry_ntiid)
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

    @WithSharedApplicationMockDS(testapp=True, users=(u'user001',), default_authenticate=False)
    @fudge.patch("nti.app.products.courseware.views.catalog_views.has_completed_course")
    def test_favorite_enrolled_course_view(self, mock_has_completed_course):
        mock_has_completed_course.is_callable().returns(False)
        self._create_and_enroll('user001')

        favorite_course_path = "/dataserver2/users/user001/Courses/EnrolledCourses/@@Favorites"
        res = self.testapp.get(favorite_course_path, status=200, extra_environ=self._make_extra_environ(username='user001')).json_body
        assert_that(res, has_entry('ItemCount', 1))

        mock_has_completed_course.is_callable().returns(True)
        res = self.testapp.get(favorite_course_path, status=200, extra_environ=self._make_extra_environ(username='user001')).json_body
        assert_that(res, has_entry('ItemCount', 1))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_upcoming_course_view(self):
        upcoming_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@"
        upcoming_course_path += VIEW_CURRENT_COURSES

        res = self.testapp.get(upcoming_course_path,
                               status=200)

        res = res.json_body
        assert_that(res, has_entry("ItemCount", 3))
        assert_that(res["Items"][0], has_entry("IsAdmin", False))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_archived_course_view(self):
        archived_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AdministeredCourses/@@" + VIEW_ARCHIVED_COURSES

        res = self.testapp.get(archived_course_path,
                               status=200)

        res = res.json_body
        assert_that(res, has_entry("ItemCount", 4))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_current_course_view(self):
        archived_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/@@" + VIEW_CURRENT_COURSES

        res = self.testapp.get(archived_course_path,
                               status=200)

        res = res.json_body
        assert_that(res, has_entry("ItemCount", 0))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_administered_course_view(self):
        administered_course_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AdministeredCourses"
        res = self.testapp.get(administered_course_path, status=200)
        res = res.json_body
        assert_that(res, has_entry("FilteredTotalItemCount", 7))

        # sorting
        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'title', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['title'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('Law and Justice', 'Introduction to Computer Programming')))

        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'title'})
        res = [x['CatalogEntry']['title'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('Introduction to Computer Programming', 'Law and Justice')))

        # StartDate
        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'StartDate', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['StartDate'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('2015-08-24T05:00:00Z', '2013-08-13T06:00:00Z')))

        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'StartDate', 'sortOrder': 'ascending'})
        res = [x['CatalogEntry']['StartDate'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('2013-08-13T06:00:00Z', '2015-08-24T05:00:00Z')))

        # EndDate
        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'EndDate', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['EndDate'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('2032-10-12T06:00:00Z', '2015-12-20T05:00:00Z')))

        res = self.testapp.get(administered_course_path, status=200, params={'sortOn': 'EndDate', 'sortOrder': 'ascending'})
        res = [x['CatalogEntry']['EndDate'] for x in res.json_body['Items']]
        assert_that((res[0], res[6]), is_(('2015-12-20T05:00:00Z', '2032-10-12T06:00:00Z')))

        # PUID
        res = self.testapp.get(administered_course_path, params={'sortOn': 'providerUniqueID', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['ProviderUniqueID'] for x in res.json_body['Items']]
        assert_that(res, contains(u'CS 1323-995', u'CS 1323-010', u'CS 1323-001',
                                  u'CS 1323', u'CLC 3403-Restricted', u'CLC 3403-01', u'CLC 3403'))

        # Last seen time - sorted by PUID without any data
        res = self.testapp.get(administered_course_path, params={'sortOn': 'lastSeenTime', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['ProviderUniqueID'] for x in res.json_body['Items']]
        assert_that(res, contains(u'CS 1323-995', u'CS 1323-010', u'CS 1323-001',
                                  u'CS 1323', u'CLC 3403-Restricted', u'CLC 3403-01', u'CLC 3403'))

        # Update last seen
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            cat = component.getUtility(ICourseCatalog)
            puid_to_course = {x.ProviderUniqueID: ICourseInstance(x) for x in cat.iterCatalogEntries()}
            user = self._get_user()
            clc_course = puid_to_course.get('CLC 3403')
            notify(UserProcessedContextsEvent(user, (clc_course.ntiid,), 1))
            clc_sub_one = puid_to_course.get('CLC 3403-01')
            notify(UserProcessedContextsEvent(user, (clc_sub_one.ntiid,), 2))
            cs_01_section = puid_to_course.get('CS 1323-001')
            notify(UserProcessedContextsEvent(user, (cs_01_section.ntiid,), 3))

        res = self.testapp.get(administered_course_path, params={'sortOn': 'lastSeenTime', 'sortOrder': 'descending'})
        res = [x['CatalogEntry']['ProviderUniqueID'] for x in res.json_body['Items']]
        assert_that(res, contains(u'CS 1323-001', u'CLC 3403-01', u'CLC 3403',
                                  u'CS 1323-995', u'CS 1323-010', u'CS 1323', u'CLC 3403-Restricted'))

        res = self.testapp.get(administered_course_path, params={'sortOn': 'lastSeenTime'})
        res = [x['CatalogEntry']['ProviderUniqueID'] for x in res.json_body['Items']]
        assert_that(res, contains(u'CLC 3403', u'CLC 3403-01', u'CS 1323-001', u'CLC 3403-Restricted',
                                  u'CS 1323',  u'CS 1323-010',  u'CS 1323-995' ))

        # Created time
        res = self.testapp.get(administered_course_path, params={'sortOn': 'createdTime',
                                                                 'sortOrder': 'descending'})
        assert_that(res.json_body['Items'], has_length(7))
