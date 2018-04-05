#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import has_entry
from hamcrest import is_not
from hamcrest import none
from hamcrest import not_none
does_not = is_not

import fudge

from nti.app.products.courseware.resources import RESOURCES

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer


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
        

        
    
