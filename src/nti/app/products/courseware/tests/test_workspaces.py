#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import empty
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import contains_inanyorder
does_not = is_not

from zope import component
from zope import lifecycleevent

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection

from nti.app.products.courseware.interfaces import ICoursesWorkspace

from nti.dataserver import traversal

from nti.app.testing.application_webtest import ApplicationLayerTest
from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.testing.matchers import is_empty
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.tests import LegacyInstructedCourseApplicationTestLayer
from nti.app.products.courseware.tests import RestrictedInstructedCourseApplicationTestLayer
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

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

	expected_workspace_length = 2
	all_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses'
	enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally...
		#res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		#assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )


		res = self.testapp.get( self.all_courses_href )
		assert_that( res.json_body, has_entry( 'Items', has_length( self.expected_workspace_length )) )
		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13T06:00:00Z')),
						 all_of( has_entries( 'StartDate', '2013-08-13T06:00:00Z',
											  'Title', 'Law and Justice' )) ) )

		for item in res.json_body['Items']:
			self.testapp.get(item['href'])

	individual_roster_accessible_to_instructor = True

	@WithSharedApplicationMockDS(users=('aaa_nextthought_com',),
								 testapp=True,
								 default_authenticate=True)
	def test_fetch_administered_courses(self):
		instructor_env = self._make_extra_environ('harp4162')

		# Note that our username comes first, but our realname (Madden Jason) comes
		# after (Johnson Steve) so we can test sorting by name
		jmadden_environ = self._make_extra_environ(username='aaa_nextthought_com')

		with mock_dataserver.mock_db_trans(self.ds):
			from nti.dataserver.users.interfaces import IFriendlyNamed
			from nti.dataserver.users import User
			steve = User.get_user('sjohnson@nextthought.com')
			jason = User.get_user('aaa_nextthought_com')
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
		self.testapp.post_json( self.enrolled_courses_href,
								'CLC 3403',
								status=201 )

		self.testapp.post_json( '/dataserver2/users/aaa_nextthought_com/Courses/EnrolledCourses',
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
															   'Username', 'aaa_nextthought_com',
															   'CourseInstance', None)) ) )
		# Sort by realname, ascending default
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa_nextthought_com') ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa_nextthought_com'),
												   has_entries('Username', self.extra_environ_default_user.lower()) ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending',
								 'batchSize': 1, 'batchStart': 0},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa_nextthought_com') ) ) )

		# Sort by username
		res = self.testapp.get( roster_link,
								{'sortOn': 'username', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa_nextthought_com') ) ) )
		res = self.testapp.get( roster_link,
								{'sortOn': 'username', 'sortOrder': 'ascending'},
								extra_environ=instructor_env)
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))
		assert_that( res.json_body, has_entry( 'Items',
											   contains(
												   has_entries('Username', 'aaa_nextthought_com'),
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
												   has_entries('Username', 'aaa_nextthought_com') ) ) )
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


		# The normal guy can't do that
		self.testapp.put_json(last_viewed_href, 5678, status=403,
							  extra_environ=jmadden_environ)
		self.testapp.get(activity_link, status=403,
						 extra_environ=jmadden_environ)

	expected_enrollment_href =  '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
	expected_catalog_entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_class = 'LegacyCommunityBasedCourseInstance'
	expected_for_credit_count = 0

	def _do_enroll(self, postdata):
		# First, we are enrolled in nothing
		res = self.testapp.get( self.enrolled_courses_href )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))
		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter. Raw strings are allowed but not preferred.

		res = self.testapp.post_json( self.enrolled_courses_href,
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
													   'TotalLegacyForCreditEnrolledCount', self.expected_for_credit_count,
													   'Outline', has_entry('Class', 'CourseOutline'),
													   'LegacyScopes', has_key('public'),
													   'LegacyScopes', has_key('restricted'),
													   'Links', has_item( has_entries( 'rel', 'CourseCatalogEntry',
																					   'href', entry_href  )) )))
		assert_that( res.location, is_( 'http://localhost' + enrollment_href ))

		# We can resolve the record by NTIID/OID
		record_ntiid = res.json_body['NTIID']
		res = self.fetch_by_ntiid(record_ntiid)
		assert_that( res.json_body,
					 has_entries(
						 'Class', 'CourseInstanceEnrollment',
						 'NTIID', record_ntiid) )

		# Now it should show up in our workspace
		res = self.testapp.get( self.enrolled_courses_href )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 ) ) )
		assert_that( res.json_body['Items'][0], has_entry( 'href', enrollment_href ) )
		assert_that( res.json_body['Items'][0], has_entry( 'RealEnrollmentStatus', is_not(none()) ) )

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


	# 3 entries: two sections of clc (main, 01), one for water
	# The third CLC section is restricted to enrolled students only
	expected_workspace_length = 3

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_search_for_scopes_when_enrolled(self):

		res = self.search_users(username='CLC')
		assert_that( res.json_body, has_entry('Items', is_empty()))

		self._do_enroll({'ntiid': self.enrollment_ntiid})

		res = self.search_users(username='CLC')
		assert_that( res.json_body, has_entry('Items', contains(has_entry('alias',
																		  'CLC 3403 - Open'))))
		scope = res.json_body['Items'][0]

		# And we can fetch it by id...
		ntres = self.fetch_by_ntiid(scope['NTIID'])
		# ...and resolve it as a user
		usres = self.resolve_user_response(username=scope['Username'])

		assert_that( ntres.json_body['NTIID'], is_(scope['NTIID']) )

		assert_that( usres.json_body['Items'][0]['NTIID'], is_(scope['NTIID']) )



	main_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	section_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice_SubInstances_01'

	def _get_main_and_sect_entries(self, res):
		main_entry, = [x for x in res.json_body['Items'] if x['NTIID'] == self.main_ntiid]
		sect_entry, = [x for x in res.json_body['Items'] if x['NTIID'] == self.section_ntiid]

		return main_entry, sect_entry

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_presentation_assets(self):
		# On disk, the main course-instance does not have any
		# presentation assets, so we fallback to the content package.
		# OTOH, section 01 does have its own assets
		res = self.testapp.get( self.all_courses_href )

		assert_that( res.json_body, has_entry( 'Items', has_length( self.expected_workspace_length )) )

		main_entry, sect_entry = self._get_main_and_sect_entries(res)

		main_assets = '/sites/platform.ou.edu/CLC3403_LawAndJustice/presentation-assets/shared/v1/'
		sect_assets = '/sites/platform.ou.edu/Courses/Fall2013/CLC3403_LawAndJustice/Sections/01/presentation-assets/shared/v1/'

		assert_that( main_entry, has_entry('PlatformPresentationResources',
										   has_item( has_entry('href', main_assets ) ) ) )
		assert_that( sect_entry,
					 has_entry('PlatformPresentationResources',
							   has_item( has_entry('href', sect_assets) ) ) )

		# If we give the global library a prefix, it manifests here too
		from nti.contentlibrary.interfaces import IContentPackageLibrary
		lib = component.getUtility(IContentPackageLibrary)
		lib.url_prefix = 'content'

		try:
			res = self.testapp.get( self.all_courses_href )
			main_entry, sect_entry = self._get_main_and_sect_entries(res)

			assert_that( main_entry,
						 has_entry('PlatformPresentationResources',
								   has_item( has_entry('href', '/content' + main_assets ) ) ) )
			assert_that( sect_entry,
						 has_entry('PlatformPresentationResources',
								   has_item( has_entry('href', '/content' + sect_assets) ) ) )

		finally:
			del lib.url_prefix


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_legacy_fields(self):
		res = self.testapp.get(self.all_courses_href)
		main_entry, sect_entry = self._get_main_and_sect_entries(res)

		assert_that( main_entry, has_entry('ContentPackageNTIID',
										   'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))
		assert_that( sect_entry, has_entry('ContentPackageNTIID',
										   'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))

		assert_that( main_entry, has_entry('LegacyPurchasableIcon',
										   '/sites/platform.ou.edu/CLC3403_LawAndJustice/images/CLC3403_promo.png' ) )
		assert_that( sect_entry, has_entry('LegacyPurchasableIcon',
										   '/sites/platform.ou.edu/CLC3403_LawAndJustice/images/CLC3403_promo.png' ) )


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_restricted_section(self):
		# Enroll him
		from nti.dataserver.users import User
		from nti.contenttypes.courses.interfaces import ICourseCatalog
		from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
		with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
			user = User.get_user('sjohnson@nextthought.com')

			cat = component.getUtility(ICourseCatalog)

			course = cat['Fall2013']['CLC3403_LawAndJustice'].SubInstances['02-Restricted']

			manager = ICourseEnrollmentManager(course)
			manager.enroll(user, scope='ForCreditDegree')

		# now our enrollment:
		res = self.testapp.get( self.enrolled_courses_href )
		assert_that( res.json_body, has_entry( 'Items',
											   has_length( 1 ) ) )
		enrollment_href = self.require_link_href_with_rel(res.json_body['Items'][0], 'edit' )
		self.testapp.get(enrollment_href)

		# and we can see it in the all courses list...
		res = self.testapp.get(self.all_courses_href)
		assert_that( res.json_body, has_entry( 'Items',
											   has_item( has_entry('ProviderUniqueID',
																   'CLC 3403-Restricted')) ) )
		assert_that( res.json_body, has_entry( 'Items',
											   has_item( has_entry('ProviderUniqueID',
																   'ENGR 1510-901')) ) )

		# ...and the remaining 'sibling' sections have vanished...
		# we get just Water and restricted
		assert_that( res.json_body, has_entry( 'Items', has_length(2) ) )



class TestRestrictedWorkspace(ApplicationLayerTest):
	layer = RestrictedInstructedCourseApplicationTestLayer
	testapp = None
	default_origin = str('http://janux.ou.edu')

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally
		#res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		#assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		assert_that( res.json_body, has_entry( 'Items', has_length( 1 )) )
		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13T06:00:00Z')) ) )

	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_enroll_unenroll_using_workspace(self):

		# First, we are enrolled in nothing
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses' )
		assert_that( res.json_body, has_entry( 'Items', is_(empty()) ) )
		assert_that( res.json_body, has_entry( 'accepts', contains('application/json')))

		# Enrolling in this one is not allowed

		self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								'CLC 3403',
								status=403 )
