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
from hamcrest import contains_inanyorder
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
from zope import lifecycleevent

from nti.testing.matchers import verifiably_provides

import os.path
import datetime
import webob.datetime_utils

from nti.app.testing.application_webtest import ApplicationLayerTest
from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection

from nti.dataserver.tests import mock_dataserver
from nti.dataserver import traversal

from nti.app.products.courseware.interfaces import ICoursesWorkspace


from . import InstructedCourseApplicationTestLayer
from . import RestrictedInstructedCourseApplicationTestLayer
from . import PersistentInstructedCourseApplicationTestLayer
from . import LegacyInstructedCourseApplicationTestLayer

class TestWorkspace(ApplicationLayerTest):

	testapp = None

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

class _AbstractEnrollingBase(object):
	testapp = None
	# This only works in the OU environment because that's where the purchasables are
	default_origin = b'http://janux.ou.edu'

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally...
		#res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		#assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )


		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 2 )) )
		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13T06:00:00Z')),
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Law and Justice' )) ) )

	individual_roster_accessible_to_instructor = True

	@WithSharedApplicationMockDS(users=('aaa@nextthought.com',),
								 testapp=True,
								 default_authenticate=True)
	def test_fetch_administered_courses(self):
		instructor_env = self._make_extra_environ('harp4162')

		# Note that our username comes first, but our realname (Madden Jason) comes
		# after (Johnson Steve) so we can test sorting by name
		jmadden_environ = self._make_extra_environ(username='aaa@nextthought.com')

		with mock_dataserver.mock_db_trans(self.ds):
			from nti.dataserver.users.interfaces import IFriendlyNamed
			from nti.dataserver.users import User
			steve = User.get_user('sjohnson@nextthought.com')
			jason = User.get_user('aaa@nextthought.com')
			IFriendlyNamed(steve).realname = 'Steve Johnson'
			IFriendlyNamed(jason).realname = 'Jason Madden'
			# Fire events so they get indexed
			lifecycleevent.modified(steve)
			lifecycleevent.modified(jason)
			lifecycleevent.modified(IFriendlyNamed(steve))
			lifecycleevent.modified(IFriendlyNamed(jason))


		res = self.testapp.get( '/dataserver2/users/harp4162/Courses/AdministeredCourses',
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'Items', has_length(1) ) )

		role = res.json_body['Items'][0]
		assert_that( role, has_entry('RoleName', 'instructor'))
		course_instance = role['CourseInstance']
		assert_that( course_instance,
					 has_entries( 'Class', self.expected_instance_class,
								  'href', self.expected_instance_href,
								  'Outline', has_entry( 'Links', has_item( has_entry( 'rel', 'contents' ))),
								  #'instructors', has_item( has_entry('Username', 'harp4162')),
								  'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry', )),
								  'Links', has_item( has_entries( 'rel', 'CourseEnrollmentRoster'))))


		roster_link = self.require_link_href_with_rel( course_instance, 'CourseEnrollmentRoster')
		activity_link = self.require_link_href_with_rel( course_instance, 'CourseActivity')

		# Put everyone in the roster
		self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								'CLC 3403',
								status=201 )

		self.testapp.post_json( '/dataserver2/users/aaa@nextthought.com/Courses/EnrolledCourses',
								'CLC 3403',
								extra_environ=jmadden_environ,
								status=201 )

		# The instructor can fetch the enrollment records directly at their usual
		# location...
		enrollment_href = self.expected_enrollment_href
		self.testapp.get(enrollment_href, extra_environ=instructor_env)
		# ...or at a location within the roster... (sometimes)
		if self.individual_roster_accessible_to_instructor:
			res = self.testapp.get(roster_link + '/sjohnson@nextthought.com', extra_environ=instructor_env)
			assert_that( res.json_body, has_entries('Class', 'CourseInstanceEnrollment',
													'Username', self.extra_environ_default_user.lower(),
													'UserProfile', has_entries( 'realname', 'Steve Johnson',
																				'NonI18NFirstName', 'Steve'),
													'CourseInstance', None,
													'href', enrollment_href))
		# ... attempting to access someone not enrolled fails
		self.testapp.get(roster_link + '/not_enrolled',
						 status=404,
						 extra_environ=instructor_env )

		# fetch the roster as the instructor
		res = self.testapp.get( roster_link,
								extra_environ=instructor_env)

		assert_that( res.json_body, has_entry( 'Items',
											   contains_inanyorder(
												   has_entries('Class', 'CourseInstanceEnrollment',
															   'Username', self.extra_environ_default_user.lower(),
															   'UserProfile', has_entries( 'realname', 'Steve Johnson',
																						   'NonI18NFirstName', 'Steve'),
															   'CourseInstance', None),
												   has_entries('Class', 'CourseInstanceEnrollment',
															   'Username', 'aaa@nextthought.com',
															   'CourseInstance', None)) ) )
		# Sort by realname, ascending default
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa@nextthought.com') ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa@nextthought.com'),
												   has_entries('Username', self.extra_environ_default_user.lower()) ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending',
								 'batchSize': 1, 'batchStart': 0},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa@nextthought.com') ) ) )

		# Sort by username
		res = self.testapp.get( roster_link,
								{'sortOn': 'username', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa@nextthought.com') ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'username', 'sortOrder': 'ascending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa@nextthought.com'),
												   has_entries('Username', self.extra_environ_default_user.lower()) ) ) )

		# Filter
		res = self.testapp.get( roster_link,
								{'filter': 'LegacyEnrollmentStatusForCredit'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'FilteredTotalItemCount', 0))
		assert_that( res.json_body, has_entry( 'Items', has_length( 0 )))

		res = self.testapp.get( roster_link,
								{'filter': 'LegacyEnrollmentStatusOpen'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'FilteredTotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items', has_length( 2 )))

		res = self.testapp.get( roster_link,
								{'usernameSearchTerm': 'aaa'}, # username
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'FilteredTotalItemCount', 1))
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa@nextthought.com') ) ) )
		res = self.testapp.get( roster_link,
								{'usernameSearchTerm': 'Steve'}, # realname
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'FilteredTotalItemCount', 1))
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower() ) ) ) )


		# fetch the activity as the instructor
		res = self.testapp.get( activity_link, extra_environ=instructor_env)

		assert_that( res.json_body, has_entry( 'TotalItemCount', 0 ) )
		assert_that( res.json_body, has_entry( 'lastViewed', 0 ) )

		last_viewed_href = self.require_link_href_with_rel( res.json_body, 'lastViewed')

		# update our viewed date
		self.testapp.put_json(last_viewed_href, 1234, extra_environ=instructor_env)
		res = self.testapp.get( activity_link, extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'lastViewed', 1234 ) )

	expected_enrollment_href =  '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
	expected_catalog_entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_class = 'LegacyCommunityBasedCourseInstance'

	def _do_enroll(self, postdata):
		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))
		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter. Raw strings are allowed but not preferred.

		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  postdata,
									  status=201 )

		# The response is a 201 created for our enrollment status
		enrollment_href = self.expected_enrollment_href
		instance_href = self.expected_instance_href
		entry_href = self.expected_catalog_entry_href

		assert_that( res.json_body,
					 has_entries(
						 'Class', 'CourseInstanceEnrollment',
						 'href', enrollment_href,
						 'CourseInstance', has_entries('Class', self.expected_instance_class,
													   'href', instance_href,
													   'TotalEnrolledCount', 1,
													   'TotalLegacyOpenEnrolledCount', 1,
													   'TotalLegacyForCreditEnrolledCount', 0,
													   'Outline', has_entry('Class', 'CourseOutline'),
													   'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																					   'href', entry_href  )) )))
		assert_that( res.location, is_( 'http://localhost' + enrollment_href ))

		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'][0], has_entry( 'href', enrollment_href ) )

		return enrollment_href, instance_href, entry_href

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):
		enrollment_href, instance_href, _ = self._do_enroll('CLC 3403')

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

	enrollment_ntiid = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'
	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_using_ntiid(self):
		self._do_enroll( {'ntiid': self.enrollment_ntiid} )



class TestLegacyWorkspace(_AbstractEnrollingBase,
						  ApplicationLayerTest):
	layer = LegacyInstructedCourseApplicationTestLayer

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_fetch_enrolled_courses_legacy(self):
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
																					 'EndDate', '2013-12-03T06:00:00Z',
																					 'Duration', 'P112D') ) ) )

		path = '/dataserver2/store/enroll_course'
		data = {'courseId': courseId}
		res = self.testapp.post_json(path, data, extra_environ=environ)
		assert_that(res.status_int, is_(204))


		# Now it should show up in our workspace
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )

		entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'], has_item( has_entries( 'Class', 'CourseInstanceEnrollment',
																	'href', '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info')) )

		course_instance = res.json_body['Items'][0]['CourseInstance']
		assert_that( course_instance,
					 has_entries( 'Class', 'LegacyCommunityBasedCourseInstance',
								  'href', '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403',
								  'Outline', has_entry( 'Links', has_item( has_entry( 'rel', 'contents' ))),
								  #'instructors', has_item( all_of(has_entry('Username', 'harp4162'),
								#								  does_not(has_key('AvatorURLChoices')),
								#								  does_not(has_key('following')),
								#								  does_not(has_key('ignoring')),
								#								  does_not(has_key('DynamicMemberships')),
								#								  does_not(has_key('opt_in_email_communication')),
								#								  does_not(has_key('NotificationCount'))) ),
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


class TestPersistentWorkspaces(_AbstractEnrollingBase,
							   ApplicationLayerTest):
	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = str('http://platform.ou.edu')
	# XXX: The order of resolution is messed up. If we install the
	# courses in the persistent platform.ou.edu, but access
	# janux.ou.edu, we only find the things registered in the
	# (non-persistent) platform.ou.edu. This is because
	# the persistent janux.ou.edu has bases:
	# (<non-persistent-janux>, <persistent platform>)
	# and getNextUtility find the utility registered in
	# <non-persistent-janux> first...


	expected_enrollment_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3ANTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	expected_instance_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice'
	expected_instance_class = 'CourseInstance'
	expected_catalog_entry_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/CourseCatalogEntry'

	enrollment_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	# An ACL issue prevents this from working (though frankly I'm not sure how it worked
	# in the legacy case.) Investigate more.
	individual_roster_accessible_to_instructor = False

class TestRestrictedWorkspace(ApplicationLayerTest):
	layer = RestrictedInstructedCourseApplicationTestLayer
	testapp = None

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally
		#res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		#assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

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
											  'StartDate', '2014-01-13T06:00:00Z')) ) )

		# XXX: Note: The purchasables no longer properly reflect this!
		# There's one too many.
		purch_res = self.testapp.get('/dataserver2/store/get_purchasables')
		assert_that( purch_res.json_body['Items'], has_length(7) )

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
