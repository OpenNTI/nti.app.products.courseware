#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
does_not = is_not

from nose.tools import assert_raises

from nti.testing.matchers import verifiably_provides

from nti.testing.time import time_monotonically_increases

from zope import component

from nti.app.products.courseware.utils import get_enrollment_options

from nti.appserver.interfaces import ILibraryPathLastModifiedProvider

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import InstructorEnrolledException

from nti.dataserver.interfaces import IAccessProvider
from nti.dataserver.interfaces import IGrantAccessException

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestEnrollmentOptions(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    all_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses'
    enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def catalog_entry(self):
        catalog = component.getUtility(ICourseCatalog)
        for entry in catalog.iterCatalogEntries():
            if entry.ntiid == self.course_ntiid:
                return entry

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_enrollment_options(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            options = get_enrollment_options(entry)
            assert_that(options, is_not(none()))
            assert_that(options, has_entry('OpenEnrollment',
                                           has_property('Enabled', is_(True))))

        self.testapp.post_json(self.enrolled_courses_href,
                               self.course_ntiid,
                               status=201)

        res = self.testapp.get(self.all_courses_href)
        assert_that
        (
            res.json_body['Items'],
            has_item
            (
                has_entry
                (
                    'EnrollmentOptions',
                    has_entry
                    (
                        'Items',
                        has_entry
                        (
                            'OpenEnrollment',
                            has_entries
                            (
                                'IsEnrolled', is_(True),
                                'IsAvailable', is_(True),
                                'MimeType', 'application/vnd.nextthought.courseware.openenrollmentoption'
                            )
                        )
                    )
                )
            )
        )


class TestEnrollment(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    username = 'sjohnson@nextthought.com'

    def _get_last_mod(self):
        user = User.get_user(self.username)
        last_mod = None
        for library_last_mod in component.subscribers((user,),
                                                      ILibraryPathLastModifiedProvider):
            last_mod = library_last_mod
        return last_mod

    @time_monotonically_increases
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_last_modified(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            last_mod = self._get_last_mod()
            assert_that(last_mod, is_(0))

        self.testapp.post_json(self.enrolled_courses_href,
                               self.course_ntiid, status=201)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            last_mod = self._get_last_mod()
            assert_that(last_mod, not_none())

            # Again
            prev_last_mod = last_mod
            last_mod = self._get_last_mod()
            assert_that(last_mod, is_(prev_last_mod))

        # Delete updates last mod
        self.testapp.delete('%s/%s' % (self.enrolled_courses_href, self.course_ntiid),
                            status=204)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            last_mod = self._get_last_mod()
            assert_that(last_mod, does_not(prev_last_mod))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_access_provider(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco')
            self._create_user(u'alana')

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entity = User.get_user(u'marco')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            access_provider = IAccessProvider(course)
            record = access_provider.grant_access(entity)
            assert_that(record, not_none())
            assert_that(record.Scope, is_(ES_PUBLIC))

            enrollments = ICourseEnrollments(course)
            assert_that(enrollments.is_principal_enrolled(entity), is_(True))

            # Purchase enrollment
            entity = User.get_user(u'alana')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            access_provider = IAccessProvider(course)
            record = access_provider.grant_access(entity,
                                                  access_context='purchased')
            assert_that(record, not_none())
            assert_that(record.Scope, is_(ES_PURCHASED))

            enrollments = ICourseEnrollments(course)
            assert_that(enrollments.is_principal_enrolled(entity), is_(True))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_instructor(self):
        enrolled_href = '/dataserver2/users/harp4162/Courses/EnrolledCourses'
        instructor_environ = self._make_extra_environ(username='harp4162')
        self.testapp.post_json(enrolled_href, self.course_ntiid,
                               extra_environ=instructor_environ,
                               status=422)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entity = User.get_user(u'harp4162')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            access_provider = IAccessProvider(course)
            with assert_raises(InstructorEnrolledException) as exc:
                access_provider.grant_access(entity)
            assert_that(exc.exception,
                        verifiably_provides(IGrantAccessException))
