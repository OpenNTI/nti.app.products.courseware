#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import empty
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.dataserver.users import User

from nti.app.products.courseware.subscribers import _get_enrollment_data
from nti.app.products.courseware.subscribers import _delete_user_enrollment_data

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestSubscribers(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	
	def catalog_entry(self):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid == self.course_ntiid:
				return entry
			
	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_delete_user_enrollment_data(self):			
		self.testapp.post_json( self.enrolled_courses_href,
								'CLC 3403',
								status=201 )
		with mock_dataserver.mock_db_trans(self.ds):
			steve = User.get_user('sjohnson@nextthought.com')
			data = _get_enrollment_data(steve)
			assert_that(data, has_entry('platform.ou.edu', is_([self.course_ntiid])))
			
		with mock_dataserver.mock_db_trans(self.ds):
			result = _delete_user_enrollment_data('sjohnson@nextthought.com', data)
			assert_that(result, has_entry('platform.ou.edu', is_([self.course_ntiid])))
			
		res = self.testapp.get(self.enrolled_courses_href, status=200)
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
