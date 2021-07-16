#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from nti.contenttypes.courses.courses import CourseSeatLimit
does_not = is_not

import fudge

from nose.tools import assert_raises

from nti.testing.matchers import verifiably_provides

from nti.testing.time import time_monotonically_increases

from zope import component
from zope import interface

from nti.app.products.courseware import VIEW_ENROLLMENT_OPTIONS

from nti.app.products.courseware.utils import get_enrollment_options

from nti.appserver.interfaces import ILibraryPathLastModifiedProvider

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED

from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.interfaces import IAccessProvider
from nti.dataserver.interfaces import IGrantAccessException

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS


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
        """
        Validate enrollment options with enrollment and seat limits.
        """
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'bunkmoreland')
        other_username = 'bunkmoreland'
        user_env = self._make_extra_environ(user=other_username)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            options = get_enrollment_options(entry)
            assert_that(options, is_not(none()))
            assert_that(options, has_entry('OpenEnrollment',
                                           has_property('Enabled', is_(True))))

        self.testapp.post_json(self.enrolled_courses_href,
                               self.course_ntiid,
                               status=201)
        def _get_course_open(username=u'sjohnson@nextthought.com', env=None):
            all_courses_href = '/dataserver2/users/%s/Courses/AllCourses' % username
            res = self.testapp.get(all_courses_href, extra_environ=env)
            courses = res.json_body['Items']
            course_res = [x for x in courses if x['NTIID'] == self.course_ntiid][0]
            open_option = course_res['EnrollmentOptions']['Items'].get(u'OpenEnrollment')
            assert_that(open_option, not_none())
            return open_option
        open_option = _get_course_open()
        assert_that(open_option, has_entries(
                                'IsEnrolled', True,
                                'IsAvailable', False,
                                'IsSeatAvailable', True,
                                'MimeType', 'application/vnd.nextthought.courseware.openenrollmentoption'))
        
        open_option = _get_course_open(other_username, user_env)
        assert_that(open_option, has_entries(
                                'IsEnrolled', False,
                                'IsAvailable', True,
                                'IsSeatAvailable', True,
                                'MimeType', 'application/vnd.nextthought.courseware.openenrollmentoption'))
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            entry.seat_limit = seat_limit = CourseSeatLimit(max_seats=1)
            seat_limit.__parent__ = entry
            assert_that(seat_limit.used_seats, is_(1))
            assert_that(seat_limit.can_user_enroll(), is_(False))
            
        open_option = _get_course_open(other_username, user_env)
        assert_that(open_option, has_entries(
                                'IsEnrolled', False,
                                'IsAvailable', True,
                                'IsSeatAvailable', False,
                                'MimeType', 'application/vnd.nextthought.courseware.openenrollmentoption'))
        
        # Cannot enroll
        user_enroll_href = '/dataserver2/users/%s/Courses/EnrolledCourses' % other_username
        res = self.testapp.post_json(user_enroll_href,
                                     self.course_ntiid,
                                     extra_environ=user_env,
                                     status=422)
        assert_that(res.json_body['code'], is_(u'CourseSeatLimitReachedException'))
        
        # Cannot redeem invite code
        code = "CI-CLC-3403"
        user_env['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        accept_url = '/dataserver2/users/%s/accept-course-invitations?code=%s' % (other_username, code)
        res = self.testapp.get(accept_url, extra_environ=user_env, status=422)
        assert_that(res.json_body['code'], is_(u'CourseSeatLimitReachedException'))
        
        # Admi *can* enroll over limit
        user_enrollments_href = '/dataserver2/users/%s/UserEnrollments' % other_username
        data = {'ntiid': self.course_ntiid,
                'scope': ES_PUBLIC}
        self.testapp.post_json(user_enrollments_href, data)
        
        open_option = _get_course_open(other_username, user_env)
        assert_that(open_option, has_entries(
                                'IsEnrolled', True,
                                'IsAvailable', False,
                                'IsSeatAvailable', False,
                                'MimeType', 'application/vnd.nextthought.courseware.openenrollmentoption'))

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            assert_that(entry.seat_limit.max_seats, is_(1))
            assert_that(entry.seat_limit.used_seats, is_(2))

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
    @fudge.patch('nti.appserver.usersearch_views._make_visibility_test')
    def test_admin_enrollment_management(self, mock_visibility):
        """
        Validate admins can drop a user from a course.
        """
        def is_visible(unused_x, unused_y=True):
            return True
        mock_visibility.is_callable().returns(is_visible)

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco')
            self._create_user(u'alana')

        enrollments_href = '/dataserver2/users/marco/UserEnrollments'

        instructor_environ = self._make_extra_environ(username='harp4162')
        enrolled_environ = self._make_extra_environ(username='marco')
        other_environ = self._make_extra_environ(username='alana')

        # Validate enrollment
        # Users cannot see rel nor can enroll (at this endpoint)
        for environ in (instructor_environ, enrolled_environ, other_environ):
            res = self.testapp.get('/dataserver2/ResolveUser/marco', extra_environ=environ)
            res = res.json_body[ITEMS][0]
            self.forbid_link_with_rel(res, 'EnrollUser')
            self.testapp.post_json(enrollments_href, {'ntiid': self.course_ntiid},
                                   extra_environ=environ, status=403)

        # NT user can
        res = self.testapp.get('/dataserver2/ResolveUser/marco')
        res = res.json_body[ITEMS][0]
        self.require_link_href_with_rel(res, 'EnrollUser')
        self.testapp.post_json(enrollments_href, {'ntiid': self.course_ntiid})

        def get_record(environ):
            res = self.testapp.get(enrollments_href, extra_environ=environ)
            res = res.json_body
            assert_that(res['Items'], has_length(1))
            return res['Items'][0]

        record = get_record(None)
        self.require_link_href_with_rel(record, 'CourseDrop')
        record = get_record(enrolled_environ)
        self.require_link_href_with_rel(record, 'CourseDrop')
        record = get_record(instructor_environ)
        self.forbid_link_with_rel(record, 'CourseDrop')

        record_href = '/dataserver2/users/marco/Courses/EnrolledCourses/%s' % self.course_ntiid

        for invalid_environ in (instructor_environ, other_environ):
            self.testapp.delete(record_href, extra_environ=invalid_environ, status=403)

        # NT admins can
        self.testapp.delete(record_href)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_access_provider(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco')
            self._create_user(u'alana')

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entity = User.get_user(u'marco')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            # Access via entry
            access_provider = IAccessProvider(entry)
            record = access_provider.grant_access(entity)
            assert_that(record, not_none())
            assert_that(record.Scope, is_(ES_PUBLIC))

            # Now by course, already enrolled
            access_provider = IAccessProvider(course)
            record = access_provider.grant_access(entity)
            assert_that(record, is_(False))

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

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            # Cannot enroll in deletd courses
            entity = User.get_user(u'harp4162')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            interface.alsoProvides(course, IDeletedCourse)
            try:
                access_provider = IAccessProvider(course, None)
                assert_that(access_provider, none())
            finally:
                interface.noLongerProvides(course, IDeletedCourse)


    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_enrollment_summary(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco')
            self._create_user(u'alana')

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            marco = User.get_user(u'marco')
            alana = User.get_user(u'alana')

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)

            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(marco)
            enrollment_manager.enroll(alana, scope=ES_CREDIT)

        stats_href = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice/CourseEnrollmentRoster/@@summary'

        instructor_environ = self._make_extra_environ(username='harp4162')
        resp = self.testapp.get(stats_href, extra_environ=instructor_environ)
        resp = resp.json_body

        assert_that(resp, has_entries('TotalEnrollments', 2,
                                      'TotalEnrollmentsByScope', has_entries('ForCredit', 1,
                                                                             'ForCreditDegree', 0,
                                                                             'ForCreditNonDegree', 0,
                                                                             'Public', 1,
                                                                             'Purchased', 0),
                                      'TotalLegacyForCreditEnrolledCount', 1,
                                      'TotalLegacyOpenEnrolledCount', 1))


    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_enrollment_option_management(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco2')

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            marco = User.get_user(u'marco2')
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(marco)

        student_env = self._make_extra_environ(username='marco2')

        course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice/'
        entry_href = '%s/%s' % (course_url, 'CourseCatalogEntry')

        res = self.testapp.get(entry_href).json_body
        entry_options = res['EnrollmentOptions'][ITEMS]
        assert_that(entry_options, has_length(4))
        for option in entry_options.values():
            # Vendor info options have no edit rel
            self.forbid_link_with_rel(option, 'edit')
        options_href = self.require_link_href_with_rel(res, VIEW_ENROLLMENT_OPTIONS)

        res = self.testapp.get(options_href).json_body
        assert_that(res[ITEMS], has_length(0))
        assert_that(res.get('AvailableEnrollmentOptions'), has_length(0))

        # Add enrollment option
        ext_dict = {'MimeType': 'application/vnd.nextthought.courseware.externalenrollmentoption',
                    'enrollment_url': u'http://testurl',
                    'title': u'Login for test site',
                    'drop_title': u'drop title',
                    'drop_description': u'drop description',
                    'drop_url': u'http://dropurl',
                    'description': u'a test login url'}
        res = self.testapp.put_json(options_href, ext_dict)
        res = res.json_body
        assert_that(res.get('href'), not_none())
        assert_that(res['NTIID'], not_none())
        assert_that(res['enrollment_url'], is_(u'http://testurl'))
        assert_that(res['title'], is_(u'Login for test site'))
        assert_that(res['description'], is_(u'a test login url'))
        assert_that(res['drop_url'], is_(u'http://dropurl'))
        assert_that(res['drop_title'], is_(u'drop title'))
        assert_that(res['drop_description'], is_(u'drop description'))
        option_edit_href = self.require_link_href_with_rel(res, 'edit')

        res = self.testapp.get(options_href).json_body
        assert_that(res[ITEMS], has_length(1))
        assert_that(res.get('AvailableEnrollmentOptions'), has_length(0))

        res = self.testapp.get(entry_href).json_body
        entry_options = res['EnrollmentOptions'][ITEMS]
        assert_that(entry_options, has_length(5))

        # Edit
        new_url = u"http://changed_url"
        res = self.testapp.put_json(option_edit_href, {'enrollment_url': new_url})
        res = res.json_body
        assert_that(res['enrollment_url'], is_(new_url))

        # 422
        self.testapp.put_json(option_edit_href,
                              {'enrollment_url': 'non_url'},
                              status=422)
        self.testapp.put_json(option_edit_href,
                              {'enrollment_url': None},
                              status=422)

        # Test access
        res = self.testapp.get(entry_href, extra_environ=student_env).json_body
        self.forbid_link_with_rel(res, VIEW_ENROLLMENT_OPTIONS)
        self.testapp.put_json(options_href, ext_dict,
                              extra_environ=student_env, status=403)
        self.testapp.put_json(option_edit_href, {'enrollment_url': new_url},
                              extra_environ=student_env,
                              status=403)

        option_res = self.testapp.get(options_href, extra_environ=student_env).json_body
        self.forbid_link_with_rel(option_res, 'edit')

        # Edit catalog entry
        self.testapp.put_json(entry_href, {'is_non_public': True})
