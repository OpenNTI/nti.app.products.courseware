#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nti.testing.matchers import is_empty

from zope import component

from zope.securitypolicy.principalrole import principalRoleManager

from nti.app.products.courseware import VIEW_COURSE_FAVORITES

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.users import User

from nti.dataserver.tests import mock_dataserver

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._workspaces import AbstractEnrollingBase

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestPersistentWorkspaces(AbstractEnrollingBase, ApplicationLayerTest):

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

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_search_for_scopes_when_enrolled(self):

		res = self.search_users(username='CLC')
		assert_that(res.json_body, has_entry('Items', is_empty()))

		self._do_enroll({'ntiid': self.enrollment_ntiid})

		res = self.search_users(username='CLC')
		assert_that(res.json_body, has_entry('Items', contains(has_entry('alias',
																		  'CLC 3403 - Open'))))
		scope = res.json_body['Items'][0]

		# And we can fetch it by id...
		ntres = self.fetch_by_ntiid(scope['NTIID'])
		# ...and resolve it as a user
		usres = self.resolve_user_response(username=scope['Username'])

		assert_that(ntres.json_body['NTIID'], is_(scope['NTIID']))

		assert_that(usres.json_body['Items'][0]['NTIID'], is_(scope['NTIID']))

	main_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	section_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice_SubInstances_01'

	def _get_main_and_sect_entries(self, res):
		main_entry, = [x for x in res.json_body['Items'] if x['NTIID'] == self.main_ntiid]
		sect_entry, = [x for x in res.json_body['Items'] if x['NTIID'] == self.section_ntiid]
		return main_entry, sect_entry

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_presentation_assets(self):
		# On disk, the main course-instance does not have any
		# presentation assets, so we fallback to the content package.
		# OTOH, section 01 does have its own assets
		res = self.testapp.get(self.all_courses_href)

		assert_that(res.json_body, has_entry('Items', has_length(greater_than_or_equal_to(self.expected_workspace_length))))

		main_entry, sect_entry = self._get_main_and_sect_entries(res)

		main_assets = '/sites/platform.ou.edu/CLC3403_LawAndJustice/presentation-assets/shared/v1/'
		sect_assets = '/sites/platform.ou.edu/Courses/Fall2013/CLC3403_LawAndJustice/Sections/01/presentation-assets/shared/v1/'

		assert_that(main_entry, has_entry('PlatformPresentationResources',
										   has_item(has_entry('href', main_assets))))
		assert_that(sect_entry,
					has_entry('PlatformPresentationResources',
							   has_item(has_entry('href', sect_assets))))

		# If we give the global library a prefix, it manifests here too
		from nti.contentlibrary.interfaces import IContentPackageLibrary
		lib = component.getUtility(IContentPackageLibrary)
		lib.url_prefix = 'content'

		try:
			res = self.testapp.get(self.all_courses_href)
			main_entry, sect_entry = self._get_main_and_sect_entries(res)

			assert_that(main_entry,
						 has_entry('PlatformPresentationResources',
								   has_item(has_entry('href', '/content' + main_assets))))
			assert_that(sect_entry,
						 has_entry('PlatformPresentationResources',
								   has_item(has_entry('href', '/content' + sect_assets))))

		finally:
			del lib.url_prefix

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_legacy_fields(self):
		res = self.testapp.get(self.all_courses_href)
		main_entry, sect_entry = self._get_main_and_sect_entries(res)

		assert_that(main_entry, has_entry('ContentPackageNTIID',
										   'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))
		assert_that(sect_entry, has_entry('ContentPackageNTIID',
										   'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))

		assert_that(main_entry, has_entry('LegacyPurchasableIcon',
										   '/sites/platform.ou.edu/CLC3403_LawAndJustice/images/CLC3403_promo.png'))
		assert_that(sect_entry, has_entry('LegacyPurchasableIcon',
										   '/sites/platform.ou.edu/CLC3403_LawAndJustice/images/CLC3403_promo.png'))

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_restricted_section(self):
		# Enroll him
		with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
			user = User.get_user('sjohnson@nextthought.com')

			cat = component.getUtility(ICourseCatalog)

			course = cat['Fall2013']['CLC3403_LawAndJustice'].SubInstances['02-Restricted']

			manager = ICourseEnrollmentManager(course)
			manager.enroll(user, scope='ForCreditDegree')

		# now our enrollment:
		res = self.testapp.get(self.enrolled_courses_href)
		assert_that(res.json_body, has_entry('Items',
											   has_length(1)))
		enrollment_href = self.require_link_href_with_rel(res.json_body['Items'][0], 'edit')
		self.testapp.get(enrollment_href)

		# and we can see it in the all courses list...
		res = self.testapp.get(self.all_courses_href)
		res = res.json_body
		assert_that(res,
					has_entry(
						'Items',
						has_item(
							has_entries(
								'ProviderUniqueID', 'CLC 3403-Restricted',
								'CatalogFamilies',
									has_entries(
										'Class', 'CatalogFamilies',
										'Items',
											has_item(
												has_entries(
													'ProviderUniqueID', 'CLC 3403',
													'Class', 'CatalogFamily',
													'Title', 'Law and Justice',
													'CatalogFamilyID', not_none(),
													'PlatformPresentationResources', not_none())))))))
		assert_that(res, has_entry('Items', has_item(has_entry('ProviderUniqueID',
																   'ENGR 1510-901'))))

		assert_that(res, has_entry('Items', has_length(6)))

		res = self.testapp.get('%s/%s' % (self.enrolled_courses_href, VIEW_COURSE_FAVORITES))
		res = res.json_body
		assert_that(res[ITEM_COUNT], is_(1))
		assert_that(res[TOTAL], is_(1))

	editor_role = 'editor'

	@WithSharedApplicationMockDS(users=('content_admin',), testapp=True)
	def test_content_admin(self):
		"""
		Make sure our global content admin has all the courses show up in
		her workspace.
		"""
		admin_environ = self._make_extra_environ(username='content_admin')

		res = self.testapp.get('/dataserver2/users/content_admin/Courses/AdministeredCourses',
								extra_environ=admin_environ)
		assert_that(res.json_body, has_entry('Items', has_length(0)))

		with mock_dataserver.mock_db_trans(self.ds):
			principalRoleManager.assignRoleToPrincipal(
								ROLE_CONTENT_ADMIN.id, 'content_admin', check=False)

		res = self.testapp.get('/dataserver2/users/content_admin/Courses/AdministeredCourses',
								extra_environ=admin_environ)
		# All non-global courses, including our non-public one.
		assert_that(res.json_body, has_entry('Items', has_length(7)))
		for course in res.json_body.get( 'Items' ):
			assert_that( course, has_entry( 'RoleName', is_( self.editor_role )))

		# Now validate our admin cannot add/update forums, topics and comments.
		course_ext = res.json_body['Items'][0]['CourseInstance']
		discussions = course_ext.get( 'Discussions' )
		self.forbid_link_with_rel(discussions, 'edit')
		self.forbid_link_with_rel(discussions, 'add')

		discussion_contents_rel = self.require_link_href_with_rel(discussions, 'contents')
		discussion_contents = self.testapp.get( discussion_contents_rel,
												extra_environ=admin_environ )
		discussion_contents = discussion_contents.json_body

		forum = discussion_contents['Items'][0]
		self.forbid_link_with_rel(forum, 'edit')
		self.forbid_link_with_rel(forum, 'add')

	@WithSharedApplicationMockDS(users=('arbitrary@nextthought.com',), testapp=True)
	def test_admin(self):
		# NT admins are automatically part of the role.
		admin_environ = self._make_extra_environ(username='arbitrary@nextthought.com')
		admin_href = '/dataserver2/users/arbitrary@nextthought.com/Courses/AdministeredCourses'
		res = self.testapp.get(admin_href, extra_environ=admin_environ)
		# All non-global courses, including our non-public one.
		assert_that(res.json_body, has_entry('Items', has_length(7)))
		for course in res.json_body.get( 'Items' ):
			assert_that( course, has_entry( 'RoleName', is_( self.editor_role )))

		res = self.testapp.get('%s/%s' % (admin_href, VIEW_COURSE_FAVORITES),
								extra_environ=admin_environ)
		res = res.json_body
		assert_that(res[ITEM_COUNT], is_(4))
		assert_that(res[TOTAL], is_(7))

		enroll_href = '/dataserver2/users/arbitrary@nextthought.com/Courses/EnrolledCourses'
		res = self.testapp.get('%s/%s' % (enroll_href, VIEW_COURSE_FAVORITES),
								extra_environ=admin_environ)
		res = res.json_body
		assert_that(res[ITEM_COUNT], is_(0))
		assert_that(res[TOTAL], is_(0))

	@WithSharedApplicationMockDS(users=('enrolled.user',), testapp=True)
	def test_enrolled_favorites(self):
		enroll_href = '/dataserver2/users/%s/Courses/EnrolledCourses' % 'enrolled.user'
		admin_href = '/dataserver2/users/%s/Courses/AdministeredCourses' % 'enrolled.user'
		enroll_faves = '%s/@@%s' % (enroll_href, VIEW_COURSE_FAVORITES)
		admin_faves = '%s/@@%s' % (admin_href, VIEW_COURSE_FAVORITES)
		environ = self._make_extra_environ(username='enrolled.user')

		res = self.testapp.get(enroll_href, extra_environ=environ)
		assert_that(res.json_body, has_entry('Items', has_length(0)))

		res = self.testapp.get(admin_faves, extra_environ=environ)
		assert_that(res.json_body[ITEM_COUNT], is_(0))
		assert_that(res.json_body[TOTAL], is_(0))

		res = self.testapp.get(enroll_faves, extra_environ=environ)
		assert_that(res.json_body[ITEM_COUNT], is_(0))
		assert_that(res.json_body[TOTAL], is_(0))

		self.testapp.post_json( enroll_href,
								{'ntiid': self.enrollment_ntiid},
								extra_environ=environ)
		res = self.testapp.get(enroll_faves, extra_environ=environ)
		assert_that(res.json_body[ITEM_COUNT], is_(1))
		assert_that(res.json_body[TOTAL], is_(1))
		record = res.json_body[ITEMS][0]
		assert_that(record,
					has_entry('href',
							  is_('%s/%s' % (enroll_href, self.enrollment_ntiid))))

