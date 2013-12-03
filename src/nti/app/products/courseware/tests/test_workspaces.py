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

from zope import component

from nti.testing.matchers import verifiably_provides

import os.path
import datetime
import webob.datetime_utils

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection

from nti.dataserver.tests import mock_dataserver
from nti.dataserver import traversal

from nti.app.products.courseware.interfaces import ICoursesWorkspace

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

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_fetch_enrolled_courses_legacy(self):
		# This is almost an integration test, checking that
		# our interfaces are properly implemented by nti.app.products.ou

		# Now that we have created the instructor user, we need to re-enumerate
		# the library so it gets noticed
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')

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

		course_instance = res.json_body['Items'][0]['CourseInstance']
		assert_that( course_instance,
					 has_entries( 'Class', 'LegacyCommunityBasedCourseInstance',
								  'href', '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403',
								  'Outline', has_entry( 'Links', has_item( has_entry( 'rel', 'contents' ))),
								  'instructors', has_item( has_entry('Username', 'harp4162')),
								  'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																  'href', entry_href  )) ))

		assert_that(res.json_body['Items'][0], has_entry(u'LegacyEnrollmentStatus', u'Open'))

		# With proper modification times
		assert_that( res, has_property( 'last_modified', not_none() ))
		assert_that( res.json_body, has_entry( 'Last Modified', greater_than( 0 )))

		# The catalog entry can be fetched too
		res = self.testapp.get( entry_href )
		assert_that( res.json_body, has_entries( 'Class', 'CourseCatalogLegacyEntry',
												 'Title', 'Law and Justice' ))

		# The outline contents can be fetched too
		outline_content_href = self.require_link_href_with_rel( course_instance['Outline'], 'contents' )
		assert_that( outline_content_href, is_('/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/Outline/contents'))
		res = self.testapp.get( outline_content_href )
		assert_that( res.last_modified, is_( datetime.datetime(2013, 10, 26, 19, 8, 15, 0, webob.datetime_utils.UTC) ))
		assert_that( res.json_body, has_length(6))
		assert_that( res.json_body[0], has_entry('title', 'Introduction'))
		assert_that( res.json_body[0], has_entry('contents', has_length(2)))



	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))
		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter.

		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		# The response is a 201 created for our enrollment status
		enrollment_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/CLC3403'
		instance_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
		entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/CLC%203403'
		assert_that( res.json_body,
					 has_entries(
						 'Class', 'CourseInstanceEnrollment',
						 'href', enrollment_href,
						 'CourseInstance', has_entries('Class', 'LegacyCommunityBasedCourseInstance',
													   'href', instance_href,
													   'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																					   'href', entry_href  )) )))
		assert_that( res.location, is_( 'http://localhost' + enrollment_href ))

		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'][0], has_entry( 'href', enrollment_href ) )

		# We can delete to drop it
		res = self.testapp.delete( enrollment_href,
								   status=204)
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
