#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import empty
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nti.app.products.courseware.tests import RestrictedInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestRestrictedWorkspace(ApplicationLayerTest):

	layer = RestrictedInstructedCourseApplicationTestLayer

	testapp = None
	default_origin = str('http://janux.ou.edu')

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally
		# res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		# assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')
		assert_that(res.json_body, has_entry('Items', has_length(greater_than_or_equal_to(1))))
		assert_that(res.json_body['Items'],
					has_items(
						 all_of(has_entries('Duration', 'P112D',
											'Title', 'Introduction to Water',
											'StartDate', '2014-01-13T06:00:00Z'))))

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_enroll_unenroll_using_workspace(self):

		# First, we are enrolled in nothing
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses')
		assert_that(res.json_body, has_entry('Items', is_(empty())))
		assert_that(res.json_body, has_entry('accepts', contains('application/json')))

		# Enrolling in this one is not allowed
		enrolled_id = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'
		self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								enrolled_id,
								status=403)
