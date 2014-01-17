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
from hamcrest import is_not
does_not = is_not
from hamcrest import has_key

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
from nti.app.products.courseware.interfaces import ICourseCatalog

class TestWorkspace(SharedApplicationTestBase):
	testapp = None

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
														  verifiably_provides( ICollection ),
														  verifiably_provides( ICollection )))

			assert_that( workspace.collections, has_items( has_property( 'name', 'AllCourses'),
														   has_property( 'name', 'EnrolledCourses' ),
														   has_property( 'name', 'AdministeredCourses' )) )

			assert_that( [traversal.resource_path(c) for c in workspace.collections],
						 has_items( course_path + '/AllCourses',
									course_path + '/EnrolledCourses' ,
									course_path + '/AdministeredCourses' ))


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

		# have to be in the site.
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 2 )) )
		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13T06:00:00')),
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Law and Justice' )) ) )

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_fetch_enrolled_courses_legacy(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# Now that we have created the instructor user, we need to re-enumerate
		# the library so it gets noticed
		with mock_dataserver.mock_db_trans(self.ds):
			cat = component.getUtility(ICourseCatalog)
			del cat._entries[:]
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )

		# (we also admin nothing)
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AdministeredCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )


		# enroll in the course using its purchasable id
		courseId = 'tag:nextthought.com,2011-10:OU-course-CLC3403LawAndJustice'
		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		purch_res = self.testapp.get('/dataserver2/store/get_purchasables')
		assert_that( purch_res.json_body, has_entry( 'Items', has_item( has_entries( 'NTIID', courseId,
																					 'StartDate', '2013-08-13',
																					 'EndDate', '2013-12-03T06:00:00',
																					 'Duration', 'P112D') ) ) )

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
								  'instructors', has_item( all_of(has_entry('Username', 'harp4162'),
																  does_not(has_key('AvatorURLChoices')),
																  does_not(has_key('following')),
																  does_not(has_key('ignoring')),
																  does_not(has_key('DynamicMemberships')),
																  does_not(has_key('opt_in_email_communication')),
																  does_not(has_key('NotificationCount'))) ),
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
		# Last mod comes from the file on disk
		assert_that( res.last_modified, is_( datetime.datetime(2014, 1, 6, 23, 20, 39, 0, webob.datetime_utils.UTC) ))
		assert_that( res.json_body, has_length(6))
		assert_that( res.json_body[0], has_entry('title', 'Introduction'))
		assert_that( res.json_body[0], has_entry('contents', has_length(2)))

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_fetch_administered_courses(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		instructor_env = self._make_extra_environ('harp4162')
		instructor_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )

		# Now that we have created the instructor user, we need to re-enumerate
		# the library so it gets noticed. We must also remove
		# a previous entry in the catalog if there is one
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			catalog = component.getUtility(ICourseCatalog)
			del catalog._entries[:] # XXX
			getattr(lib, 'contentPackages')


		res = self.testapp.get( '/dataserver2/users/harp4162/Courses/AdministeredCourses',
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'Items', has_length(1) ) )

		role = res.json_body['Items'][0]
		assert_that( role, has_entry('RoleName', 'instructor'))
		course_instance = role['CourseInstance']
		assert_that( course_instance,
					 has_entries( 'Class', 'LegacyCommunityBasedCourseInstance',
								  'href', '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403',
								  'Outline', has_entry( 'Links', has_item( has_entry( 'rel', 'contents' ))),
								  'instructors', has_item( has_entry('Username', 'harp4162')),
								  'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry', )),
								  'Links', has_item( has_entries( 'rel', 'CourseEnrollmentRoster'))))


		roster_link = self.require_link_href_with_rel( course_instance, 'CourseEnrollmentRoster')
		activity_link = self.require_link_href_with_rel( course_instance, 'CourseActivity')

		# Put someone in the roster
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		# fetch the roster as the instructor
		res = self.testapp.get( roster_link, extra_environ=instructor_env)

		assert_that( res.json_body, has_entry( 'Items', contains( has_entries('Class', 'CourseInstanceEnrollment',
																			  'Username', self.extra_environ_default_user.lower(),
																			  'CourseInstance', None) ) ) )

		# fetch the activity as the instructor
		res = self.testapp.get( activity_link, extra_environ=instructor_env)

		assert_that( res.json_body, has_entry( 'TotalItemCount', 0 ) )
		assert_that( res.json_body, has_entry( 'lastViewed', 0 ) )

		last_viewed_href = self.require_link_href_with_rel( res.json_body, 'lastViewed')

		# update our viewed date
		self.testapp.put_json(last_viewed_href, 1234, extra_environ=instructor_env)
		res = self.testapp.get( activity_link, extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'lastViewed', 1234 ) )

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))
		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter. Raw strings are allowed but not preferred.

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
													   #'TotalEnrolledCount', 1,
													   'Outline', has_entry('Class', 'CourseOutline'),
													   'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																					   'href', entry_href  )) )))
		assert_that( res.location, is_( 'http://localhost' + enrollment_href ))

		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'][0], has_entry( 'href', enrollment_href ) )

		# Because we are an admin, we can also access the global roster that will show us in it
		res = self.testapp.get('/dataserver2/@@AllEnrollments.csv')
		# We have no email address at this point
		assert_that( res.text, is_('sjohnson@nextthought.com,,,,Law and Justice\r\n'))

		# give us one
		self.testapp.put_json( '/dataserver2/users/sjohnson@nextthought.com/++fields++email',
							   'jason.madden@nextthought.com' )
		# Along with a non-ascii alias
		self.testapp.put_json( '/dataserver2/users/sjohnson@nextthought.com/++fields++alias',
							   'Gr\xe8y')

		# We find this both in the global list, and in the specific list
		# if we filter to open enrollments
		for url in '/dataserver2/@@AllEnrollments.csv?LegacyEnrollmentStatus=Open', instance_href + '/Enrollments.csv?LegacyEnrollmentStatus=Open':
			res = self.testapp.get(url)
			assert_that( res.text, is_('sjohnson@nextthought.com,Gr\xe8y,,jason.madden@nextthought.com,Law and Justice\r\n'))

		# And we find nothing if we filter to for credit enrollments
		for url in '/dataserver2/@@AllEnrollments.csv?LegacyEnrollmentStatus=ForCredit', instance_href + '/Enrollments.csv?LegacyEnrollmentStatus=ForCredit':
			res = self.testapp.get(url)
			assert_that( res.text, is_('') )

		# We can delete to drop it
		res = self.testapp.delete( enrollment_href,
								   status=204)
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )

		# No longer in the enrolled list
		res = self.testapp.get('/dataserver2/@@AllEnrollments.csv')
		assert_that( res.text, is_('') )


		# If we post a non-existant class, it fails gracefully
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'This Class Does Not Exist',
									  status=404 )

		# For convenience, we can use a dictionary
		self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								{'ProviderUniqueID': 'CLC 3403'},
								status=201 )


class TestRestrictedWorkspace(SharedApplicationTestBase):
	testapp = None

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		lib = Library(
					paths=(os.path.join(
									os.path.dirname(__file__),
									'RestrictedLibrary',
									'IntroWater'),
						   os.path.join(
								   os.path.dirname(__file__),
								   'RestrictedLibrary',
								   'CLC3403_LawAndJustice')
				   ))
		return lib

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

		# have to be in the site.
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )) )
		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13T06:00:00')) ) )

		purch_res = self.testapp.get('/dataserver2/store/get_purchasables')
		assert_that( purch_res.json_body['Items'], has_length(6) ) # TODO: Really verify that it's the CLC missing

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))

		# Enrolling in this one is not allowed

		self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								'CLC 3403',
								status=403 )
