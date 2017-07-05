#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entries
from hamcrest import assert_that

import json

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseEdits(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """
    
    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = str('http://janux.ou.edu')

    course_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/CourseCatalogEntry'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_edit(self):
        instructor_environ = self._make_extra_environ()

        res = self.testapp.get(
            self.course_path,
            extra_environ=instructor_environ)
        res_dict = json.loads(res.body)

        # Be sure the original course was returned correctly
        assert_that(res_dict, has_entries("Title", "Law and Justice",
                                          "ProviderDepartmentTitle", "Department of Classics and Letters at the University of Oklahoma",
                                          "Description", ("What makes a law just? In this course we explore fundamental "
                                                          "questions about the nature of law and justice through engagement "
                                                          "with the great texts of the western tradition. The course covers "
                                                          "the sweep of documented history in five units: classical Greece, "
                                                          "ancient Rome, early Christianity, the Enlightenment, and the age of market "
                                                          "capitalism. The focus of this course is on law, because law is the meeting "
                                                          "point between the theory and practice of justice. With  Aristotle's Politics "
                                                          "as our principal guide, we will participate in an ancient and enduring "
                                                          "conversation about the nature of law and justice.")))

        new_course_info = {"Title": "Another Course",
                           "ProviderDepartmentTitle": "Department of Austin Graham",
                           "Description": "Yet another course"}

        edit_path = self.course_path + "/edit"
        
        # Edit the course with the new information
        self.testapp.post(edit_path,
                          json.dumps(new_course_info),
                          extra_environ=instructor_environ,
                          status=204)

        res = self.testapp.get(
            self.course_path,
            extra_environ=instructor_environ)

        res_dict = json.loads(res.body)
        
        # Be sure the new information is contained in the course
        assert_that(res_dict, has_entries("Title", "Another Course",
                                          "ProviderDepartmentTitle", "Department of Austin Graham",
                                          "Description", "Yet another course"))
        
        new_course_info = {"DummyAttribute": "Wrong"}
        
        # If the arguments are bad, 400 should be returned.
        self.testapp.post(edit_path,
                          json.dumps(new_course_info),
                          extra_environ=instructor_environ,
                          status=400)

