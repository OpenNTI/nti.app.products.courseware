#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import has_property
from hamcrest import has_length
from hamcrest import has_entry
from hamcrest import all_of
from hamcrest import has_entries
from hamcrest import empty
from hamcrest import not_none
from hamcrest import greater_than

from nti.testing import base
from nti.testing import matchers
from nti.testing.matchers import verifiably_provides

import os.path

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS


from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection
from ..interfaces import ICoursesWorkspace
from nti.dataserver import users

from nti.dataserver.tests import mock_dataserver
from nti.dataserver import traversal

class TestWorkspace(SharedApplicationTestBase):

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		lib = Library(
					paths=(os.path.join(
									os.path.dirname(__file__),
									'Library',
									'IntroWater'),
						   os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice')
				   ))
		return lib

	@WithSharedApplicationMockDS
	def test_workspace_links_in_service(self):
		with mock_dataserver.mock_db_trans(self.ds):
			user = self._create_user( username=self.extra_environ_default_user )
			service = IUserService(user)

			workspaces = service.workspaces

			assert_that( workspaces, has_item( verifiably_provides( ICoursesWorkspace )))

			workspace = [x for x in workspaces if ICoursesWorkspace.providedBy(x)][0]

			course_path = '/dataserver2/users/sjohnson%40nextthought.COM/Courses'
			assert_that( traversal.resource_path( workspace ),
						 is_( course_path ) )

			assert_that( workspace.collections, contains( verifiably_provides( ICollection ),
														  verifiably_provides( ICollection )))

			assert_that( workspace.collections, has_items( has_property( 'name', 'AllCourses'),
														   has_property( 'name', 'EnrolledCourses' )) )

			assert_that( [traversal.resource_path(c) for c in workspace.collections],
						 has_items( course_path + '/AllCourses',
									course_path + '/EnrolledCourses' ))


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )

		assert_that( res.json_body, has_entry( 'Items', has_length( 2 )) )

		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13')),
						 all_of( has_entries( 'Duration', None,
											  'Title', 'Law and Justice' )) ) )

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_enrolled_courses_legacy(self):
		# This is almost an integration test, checking that
		# our interfaces are properly implemented by nti.app.products.ou

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )

		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )


		# enroll in the course using its purchasable id
		courseId = 'tag:nextthought.com,2011-10:OU-course-CLC3403LawAndJustice'
		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'


		path = '/dataserver2/store/enroll_course'
		data = {'courseId': courseId}
		res = self.testapp.post_json(path, data, extra_environ=environ)
		assert_that(res.status_int, is_(204))

		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )

		entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/CLC%203403'
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'], has_item( has_entries( 'Class', 'CourseInstanceEnrollment',
																	'href', '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/CLC3403')) )

		assert_that( res.json_body['Items'][0]['CourseInstance'],
					 has_entries( 'Class', 'CourseInstance',
								  'href', '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403',
								  'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																  'href', entry_href  )) ))
		# With proper modification times
		assert_that( res, has_property( 'last_modified', not_none() ))
		assert_that( res.json_body, has_entry( 'Last Modified', greater_than( 0 )))

		# The entry can be fetched too
		res = self.testapp.get( entry_href )
		assert_that( res.json_body, has_entries( 'Class', 'CourseCatalogLegacyEntry',
												 'Title', 'Law and Justice' ))


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )

		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter.

		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		# The response is a 201 created, with the
		# apparent effect of creating the course instance
		instance_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
		entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/CLC%203403'
		assert_that( res.json_body,
					 has_entries( 'Class', 'CourseInstance',
								  'href', instance_href,
								  'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																  'href', entry_href  )) ))
		assert_that( res.location, is_( 'http://localhost' + instance_href ))

		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )

		# We can delete to drop it
		res = self.testapp.delete( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses/CLC%203403',
								   status=204)
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
