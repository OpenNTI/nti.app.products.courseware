#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import has_entry
from hamcrest import has_item
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import not_none
does_not = is_not

import fudge

from zope.component.hooks import getSite

from zope.security.interfaces import IParticipation
from zope.security.management import endInteraction
from zope.security.management import newInteraction
from zope.security.management import restoreInteraction

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.courseware.resources import RESOURCES

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.externalization.externalization import toExternalObject

from nti.app.products.courseware.decorators import _CourseInstanceEnrollmentLastSeenDecorator

from nti.app.products.courseware.workspaces import DefaultCourseInstanceEnrollment

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.enrollment import DefaultCourseInstanceEnrollmentRecord

from nti.coremetadata.interfaces import IContextLastSeenContainer

from nti.dataserver.authorization import ACT_CONTENT_EDIT
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

class TestCoursePreviewExternalization(ApplicationLayerTest):
    """
    Validate courses in preview mode hide features from enrolled students,
    but still expose them for admins.
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_href = '/dataserver2/Objects/tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
    course_ntiid = None

    enrolled_courses_href = '/dataserver2/users/test_student/Courses/EnrolledCourses'
    enrollment_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def _do_enroll(self, environ):
        return self.testapp.post_json(self.enrolled_courses_href,
                                      {'ntiid': self.enrollment_ntiid},
                                      status=201,
                                      extra_environ=environ)

    def _get_course_ext(self, environ):
        if not self.course_ntiid:
            entry = self.testapp.get(self.course_href, extra_environ=environ)
            entry = entry.json_body
            self.course_ntiid = entry.get('CourseNTIID')
        result = self.testapp.get('/dataserver2/Objects/%s' % self.course_ntiid,
                                  extra_environ=environ)
        return result.json_body

    def _test_course_ext(self, environ, is_visible=True):
        if is_visible:
            to_check = not_none
            link_check = self.require_link_href_with_rel
        else:
            to_check = none
            link_check = self.forbid_link_with_rel
        course_ext = self._get_course_ext(environ)

        assert_that(course_ext.get('LegacyScopes'), to_check())
        assert_that(course_ext.get('SharingScopes'), to_check())
        assert_that(course_ext.get('Discussions'), to_check())

        for rel in (RESOURCES, 'Pages'):
            link_check(course_ext, rel)

        outline = course_ext.get('Outline')
        link_check(outline, 'contents')

    @WithSharedApplicationMockDS(users=('test_student',), testapp=True)
    @fudge.patch('nti.app.products.courseware.utils.PreviewCourseAccessPredicate._is_preview')
    def test_preview_decorators(self, mock_is_preview):
        mock_is_preview.is_callable().returns(False)
        student_env = self._make_extra_environ('test_student')
        instructor_env = self._make_extra_environ('harp4162')
        self._do_enroll(student_env)

        # Base case
        self._test_course_ext(student_env, is_visible=True)

        # Preview mode
        mock_is_preview.is_callable().returns(True)
        self._test_course_ext(student_env, is_visible=False)

        # Preview mode w/instructor
        self._test_course_ext(instructor_env, is_visible=True)

    @WithSharedApplicationMockDS(users=('test_student',), testapp=True)
    def test_type_on_instance_link(self):
        student_env = self._make_extra_environ('test_student')
        enrollment = self._do_enroll(student_env).json_body

        link = self.link_with_rel(enrollment, 'CourseInstance')
        assert_that(link, not_none())
        assert_that(link, has_entry('type', 'application/vnd.nextthought.courses.courseinstance'))
        

class TestDecorators(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_entry_href = '/dataserver2/Objects/tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def _decorate(self, decorator, context, request=None):
        external = toExternalObject(context, decorate=False)
        decorator = decorator(context, request)
        decorator.decorateExternalObject(context, external)
        return external

    @WithMockDSTrans
    @fudge.patch("nti.contenttypes.courses.courses.to_external_ntiid_oid")
    def test_CourseInstanceEnrollmentDecorator(self, mock_to_external_ntiid_oid):
        mock_to_external_ntiid_oid.is_callable().returns("ntiid_abc")
        user = self._create_user(username=u'test001')
        record = DefaultCourseInstanceEnrollmentRecord(Principal=user)

        class _MockStorage(object):
            pass
        record.__parent__ = _MockStorage()
        record.__parent__.__parent__ = CourseInstance()

        enrollment = DefaultCourseInstanceEnrollment(record)

        _container = IContextLastSeenContainer(user, None)
        _container.append(u'ntiid_abc', 1533445200)

        external = self._decorate(_CourseInstanceEnrollmentLastSeenDecorator, enrollment)
        assert_that(external['LastSeenTime'].strftime('%Y-%m-%d %H:%M:%S'), is_("2018-08-05 05:00:00"))

    @WithSharedApplicationMockDS(users=('test_student', 'admin001@nextthought.com', 'site_username'), testapp=True)
    def test_CourseTabPreferencesLinkDecorator(self):
        student_env = self._make_extra_environ('test_student')
        instructor_env = self._make_extra_environ('harp4162')
        admin_env = self._make_extra_environ('admin001@nextthought.com')
        site_admin_evn = self._make_extra_environ('site_username')

        def _course_ntiid(environ):
            entry = self.testapp.get(self.course_entry_href, extra_environ=environ)
            return entry.json_body['CourseNTIID']

        course_ntiid = _course_ntiid(admin_env)
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, 'site_username')

            course = find_object_with_ntiid(course_ntiid)
            assert_that(has_permission(ACT_READ, course, 'test_student'), is_(True))
            assert_that(has_permission(ACT_CONTENT_EDIT, course, 'test_student'), is_(False))

            assert_that(has_permission(ACT_READ, course, 'harp4162'), is_(True))
            assert_that(has_permission(ACT_CONTENT_EDIT, course, 'harp4162'), is_(True))

            assert_that(has_permission(ACT_READ, course, 'admin001@nextthought.com'), is_(True))
            assert_that(has_permission(ACT_CONTENT_EDIT, course, 'admin001@nextthought.com'), is_(True))

            endInteraction()
            try:
                newInteraction(IParticipation(User.get_user('site_username')))
                assert_that(has_permission(ACT_READ, course, 'site_username'), is_(True))
                assert_that(has_permission(ACT_CONTENT_EDIT, course, 'site_username'), is_(True))
            finally:
                restoreInteraction()

        # Only nextthought admin could access the edit link.
        course_href = '/dataserver2/NTIIDs/' + course_ntiid
        result = self.testapp.get(course_href, extra_environ=admin_env)
        rels = [x['rel'] for x in result.json_body['Links']]
        assert_that(rels, has_item('GetCourseTabPreferences'))
        assert_that(rels, has_item('UpdateCourseTabPreferences'))

        result = self.testapp.get(course_href, extra_environ=instructor_env)
        rels = [x['rel'] for x in result.json_body['Links']]
        assert_that(rels, has_item('GetCourseTabPreferences'))
        assert_that(rels, is_not(has_item('UpdateCourseTabPreferences')))

        result = self.testapp.get(course_href, extra_environ=student_env)
        rels = [x['rel'] for x in result.json_body['Links']]
        assert_that(rels, has_item('GetCourseTabPreferences'))
        assert_that(rels, is_not(has_item('UpdateCourseTabPreferences')))

        result = self.testapp.get(course_href, extra_environ=site_admin_evn)
        rels = [x['rel'] for x in result.json_body['Links']]
        assert_that(rels, has_item('GetCourseTabPreferences'))
        assert_that(rels, is_not(has_item('UpdateCourseTabPreferences')))
