#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
does_not = is_not

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.app.products.courseware.utils import get_enrollment_options

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestEnrollmentOptions(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	
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
			
		self.testapp.post_json( self.enrolled_courses_href,
								'CLC 3403',
								status=201 )
		
		res = self.testapp.get( self.all_courses_href )
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
