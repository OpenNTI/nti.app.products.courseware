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
from hamcrest import contains_inanyorder
from hamcrest import greater_than_or_equal_to
does_not = is_not

import csv
from urllib import unquote

from six import StringIO

from zope import lifecycleevent

from nti.app.products.courseware import VIEW_COURSE_RECURSIVE
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE_BUCKET

from nti.dataserver.users import User

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

class AbstractEnrollingBase(object):

	testapp = None
	# This only works in the OU environment because that's where the purchasables are
	default_origin = b'http://janux.ou.edu'

	expected_workspace_length = 2
	all_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses'
	enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_fetch_all_courses(self):
		# XXX: Our layer is registering these globally...
		# res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )
		# Nothing by default
		# assert_that( res.json_body, has_entry( 'Items', has_length( 0 )) )

		res = self.testapp.get(self.all_courses_href)
		assert_that(res.json_body, has_entry('Items',
											  has_length(greater_than_or_equal_to(self.expected_workspace_length))))
		assert_that(res.json_body['Items'],
					 has_items(
						 all_of(has_entries('Duration', 'P112D',
											'Title', 'Introduction to Water',
											'StartDate', '2014-01-13T06:00:00Z')),
						 all_of(has_entries('StartDate', '2013-08-13T06:00:00Z',
											'Title', 'Law and Justice'))))

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

			steve = User.get_user('sjohnson@nextthought.com')
			jason = User.get_user('aaa_nextthought_com')
			IFriendlyNamed(steve).realname = 'Steve Johnson'
			IFriendlyNamed(jason).realname = 'Jason Madden'
			# Fire events so they get indexed
			lifecycleevent.modified(steve)
			lifecycleevent.modified(jason)
			lifecycleevent.modified(IFriendlyNamed(steve))
			lifecycleevent.modified(IFriendlyNamed(jason))

		res = self.testapp.get('/dataserver2/users/harp4162/Courses/AdministeredCourses',
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('Items', has_length(1)))

		role = res.json_body['Items'][0]
		assert_that(role, has_entry('RoleName', 'instructor'))
		course_instance = role['CourseInstance']

		assert_that(course_instance,
					has_entries('Class', self.expected_instance_class,
								'href', unquote(self.expected_instance_href),
								'Outline', has_entry('Links', has_item(has_entry('rel', 'contents'))),
								# 'instructors', has_item( has_entry('Username', 'harp4162')),
								'Links', has_item(has_entry('rel', 'CourseCatalogEntry')),
								'Links', has_item(has_entry('rel', VIEW_COURSE_RECURSIVE)),
								'Links', has_item(has_entry('rel', 'CourseEnrollmentRoster')),
								'Links', has_item(has_entry('rel', VIEW_COURSE_RECURSIVE_BUCKET)),
								'Links', has_item(has_entry('rel', 'Pages'))))

		roster_link = self.require_link_href_with_rel(course_instance, 'CourseEnrollmentRoster')
		activity_link = self.require_link_href_with_rel(course_instance, 'CourseActivity')

		# Put everyone in the roster
		enrolled_course_id = getattr( self, 'enrollment_ntiid', None ) \
							 or 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'
		self.testapp.post_json( self.enrolled_courses_href,
								enrolled_course_id,
								status=201)

		self.testapp.post_json('/dataserver2/users/aaa_nextthought_com/Courses/EnrolledCourses',
								enrolled_course_id,
								extra_environ=jmadden_environ,
								status=201)

		# The instructor can try to fetch the enrollment records directly at their usual
		# location...
		enrollment_href = self.expected_enrollment_href
		self.testapp.get(enrollment_href, extra_environ=instructor_env)
		# ...but sometimes at a location within the roster...
		if self.individual_roster_accessible_to_instructor:
			res = self.testapp.get(roster_link + '/sjohnson@nextthought.com', extra_environ=instructor_env)
			assert_that(res.json_body, has_entries('Class', 'CourseInstanceEnrollment',
													'Username', self.extra_environ_default_user.lower(),
													'UserProfile', has_entries('realname', 'Steve Johnson',
																				'NonI18NFirstName', 'Steve'),
													'CourseInstance', None,
													'href', enrollment_href))
		# ... attempting to access someone not enrolled fails
		self.testapp.get(roster_link + '/not_enrolled',
						 status=404,
						 extra_environ=instructor_env)

		# fetch the roster as the instructor
		res = self.testapp.get(roster_link,
								extra_environ=instructor_env)

		assert_that(res.json_body, has_entry('Items',
											  contains_inanyorder(
												   has_entries('Class', 'CourseInstanceEnrollment',
															   'Username', self.extra_environ_default_user.lower(),
															   'UserProfile', has_entries('realname', 'Steve Johnson',
																						   'NonI18NFirstName', 'Steve'),
															   'CourseInstance', None),
												   has_entries('Class', 'CourseInstanceEnrollment',
															   'Username', 'aaa_nextthought_com',
															   'CourseInstance', None))))
		# Sort by realname, ascending default
		res = self.testapp.get(roster_link,
								{'sortOn': 'realname'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa_nextthought_com'))))
		res = self.testapp.get(roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', 'aaa_nextthought_com'),
												   has_entries('Username', self.extra_environ_default_user.lower()))))
		res = self.testapp.get(roster_link,
								{'sortOn': 'realname', 'sortOrder': 'descending',
								 'batchSize': 1, 'batchStart': 0},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items', has_length(1)))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', 'aaa_nextthought_com'))))

		# Sort by username
		res = self.testapp.get(roster_link,
								{'sortOn': 'username', 'sortOrder': 'descending'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items',
											   contains(
												   has_entries('Username', self.extra_environ_default_user.lower()),
												   has_entries('Username', 'aaa_nextthought_com'))))
		res = self.testapp.get(roster_link,
								{'sortOn': 'username', 'sortOrder': 'ascending'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', 'aaa_nextthought_com'),
												   has_entries('Username', self.extra_environ_default_user.lower()))))

		# Filter
		res = self.testapp.get(roster_link,
								{'filter': 'LegacyEnrollmentStatusForCredit'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('FilteredTotalItemCount', 0))
		assert_that(res.json_body, has_entry('Items', has_length(0)))

		res = self.testapp.get(roster_link,
								{'filter': 'LegacyEnrollmentStatusOpen'},
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('FilteredTotalItemCount', 2))
		assert_that(res.json_body, has_entry('Items', has_length(2)))

		res = self.testapp.get(roster_link,
								{'usernameSearchTerm': 'aaa'},  # username
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('FilteredTotalItemCount', 1))
		assert_that(res.json_body, has_entry('Items', has_length(1)))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', 'aaa_nextthought_com'))))
		res = self.testapp.get(roster_link,
								{'usernameSearchTerm': 'Steve'},  # realname
								extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('TotalItemCount', 2))
		assert_that(res.json_body, has_entry('FilteredTotalItemCount', 1))
		assert_that(res.json_body, has_entry('Items', has_length(1)))
		assert_that(res.json_body, has_entry('Items',
											  contains(
												   has_entries('Username', self.extra_environ_default_user.lower()))))


		# fetch the activity as the instructor
		res = self.testapp.get(activity_link, extra_environ=instructor_env)

		assert_that(res.json_body, has_entry('TotalItemCount', 0))
		assert_that(res.json_body, has_entry('lastViewed', 0))

		last_viewed_href = self.require_link_href_with_rel(res.json_body, 'lastViewed')

		# update our viewed date
		self.testapp.put_json(last_viewed_href, 1234, extra_environ=instructor_env)
		res = self.testapp.get(activity_link, extra_environ=instructor_env)
		assert_that(res.json_body, has_entry('lastViewed', 1234))


		# The normal guy can't do that
		self.testapp.put_json(last_viewed_href, 5678, status=403,
							  extra_environ=jmadden_environ)
		self.testapp.get(activity_link, status=403,
						 extra_environ=jmadden_environ)

	expected_enrollment_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
	expected_catalog_entry_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/CourseCatalog/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'
	expected_instance_class = 'LegacyCommunityBasedCourseInstance'
	expected_for_credit_count = 0

	def _do_enroll(self, postdata):
		# First, we are enrolled in nothing
		res = self.testapp.get(self.enrolled_courses_href)
		assert_that(res.json_body, has_entry('Items', is_(empty())))
		assert_that(res.json_body, has_entry('accepts', contains('application/json')))
		# We can POST to EnrolledCourses to add a course, assuming we're allowed
		# Right now, we accept any value that the course catalog can accept;
		# this will probably get stricter. Raw strings are allowed but not preferred.

		res = self.testapp.post_json(self.enrolled_courses_href,
									  postdata,
									  status=201)

		# The response is a 201 created for our enrollment status
		enrollment_href = self.expected_enrollment_href
		instance_href = self.expected_instance_href
		entry_href = self.expected_catalog_entry_href

		assert_that(res.json_body,
					has_entries(
						'Class', 'CourseInstanceEnrollment',
						'href', unquote(enrollment_href),
						'CourseInstance', has_entries('Class', self.expected_instance_class,
													   'href', unquote(instance_href),
													   'TotalEnrolledCount', 1,
													   'TotalLegacyOpenEnrolledCount', 1,
													   'TotalLegacyForCreditEnrolledCount', self.expected_for_credit_count,
													   'Outline', has_entry('Class', 'CourseOutline'),
													   'LegacyScopes', has_key('public'),
													   'LegacyScopes', has_key('restricted'),
													   'Links', has_item(has_entries('rel', 'CourseCatalogEntry',
																					 'href', unquote(entry_href))))))
		assert_that(res.location, is_('http://localhost' + unquote(enrollment_href)))

		# We can resolve the record by NTIID/OID
		record_ntiid = res.json_body['NTIID']
		res = self.fetch_by_ntiid(record_ntiid)
		assert_that(res.json_body,
					has_entries(
						 'Class', 'CourseInstanceEnrollment',
						 'NTIID', record_ntiid))

		# Now it should show up in our workspace
		res = self.testapp.get(self.enrolled_courses_href)
		assert_that(res.json_body, has_entry('Items', has_length(1)))
		assert_that(res.json_body['Items'][0], has_entry('href', unquote(enrollment_href)))
		assert_that(res.json_body['Items'][0], has_entry('RealEnrollmentStatus', is_not(none())))

		return enrollment_href, instance_href, entry_href

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_enroll_unenroll_using_workspace(self):
		enrolled_course_id = getattr( self, 'enrollment_ntiid', None ) \
						or 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'
		enrollment_href, instance_href, _ = self._do_enroll( enrolled_course_id )

		# Because we are an admin, we can also access the global roster that will show us in it
		res = self.testapp.get('/dataserver2/@@AllEnrollments.csv')
		enrollments = tuple( csv.DictReader( StringIO( res.body ) ) )
		assert_that( enrollments, has_length( 1 ))
		enrollment = enrollments[0]
		# We have no email address at this point
		assert_that( enrollment, has_entries( 'username', 'sjohnson@nextthought.com',
											  'alias', '',
											  'realname', '',
											  'email', '',
											  'courses', 'Law and Justice'))

		# give us one
		self.testapp.put_json('/dataserver2/users/sjohnson@nextthought.com/++fields++email',
							   'jason.madden@nextthought.com')
		# Along with a non-ascii alias
		self.testapp.put_json('/dataserver2/users/sjohnson@nextthought.com/++fields++alias',
							   'Gr\xe8y')

		# We find this both in the global list, and in the specific list
		# if we filter to open enrollments
		for url in ('/dataserver2/@@AllEnrollments.csv?LegacyEnrollmentStatus=Open',
					instance_href + '/Enrollments.csv?LegacyEnrollmentStatus=Open'):
			res = self.testapp.get(url)
			enrollments = tuple( csv.DictReader( StringIO( res.body ) ) )
			assert_that( enrollments, has_length( 1 ))
			enrollment = enrollments[0]
			enrollment = {k: v.decode( 'utf-8' ) for k, v in enrollment.items()}
			assert_that( enrollment, has_entries( 'username', 'sjohnson@nextthought.com',
												  'alias', 'Gr\xe8y',
												  'realname', '',
												  'email', 'jason.madden@nextthought.com',
												  'courses', 'Law and Justice'))

		# And we find nothing if we filter to for credit enrollments
		for url in ('/dataserver2/@@AllEnrollments.csv?LegacyEnrollmentStatus=ForCredit',
					instance_href + '/Enrollments.csv?LegacyEnrollmentStatus=ForCredit'):
			res = self.testapp.get(url)
			enrollments = tuple( csv.DictReader( StringIO( res.body ) ) )
			assert_that( enrollments, has_length( 0 ))

		# We can delete to drop it
		res = self.testapp.delete(enrollment_href,
								   status=204)
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses')
		assert_that(res.json_body, has_entry('Items', is_(empty())))

		# No longer in the enrolled list
		res = self.testapp.get('/dataserver2/@@AllEnrollments.csv')
		enrollments = tuple( csv.DictReader( StringIO( res.body ) ) )
		assert_that( enrollments, has_length( 0 ))

		# If we post a non-existant class, it fails gracefully
		res = self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'This Class Does Not Exist',
									  status=404)

		# For convenience, we can use a dictionary
		self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								{'ProviderUniqueID': self.enrollment_ntiid},
								status=201)

	enrollment_ntiid = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'
	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_enroll_using_ntiid(self):
		self._do_enroll({'ntiid': self.enrollment_ntiid})

_AbstractEnrollingBase = AbstractEnrollingBase

