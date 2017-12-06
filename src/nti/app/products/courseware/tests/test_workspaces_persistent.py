#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

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
from hamcrest import contains_inanyorder
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nti.testing.matchers import is_empty

import fudge

from zope import component

from zope.securitypolicy.principalrole import principalRoleManager

from nti.app.products.courseware import VIEW_COURSE_BY_TAG
from nti.app.products.courseware import VIEW_COURSE_FAVORITES
from nti.app.products.courseware import VIEW_ENROLLED_WINDOWED
from nti.app.products.courseware import VIEW_ALL_COURSES_WINDOWED
from nti.app.products.courseware import VIEW_ALL_ENTRIES_WINDOWED
from nti.app.products.courseware import VIEW_ADMINISTERED_WINDOWED

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._workspaces import AbstractEnrollingBase

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.appserver.workspaces import VIEW_CATALOG_POPULAR
from nti.appserver.workspaces import VIEW_CATALOG_FEATURED

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.users import User

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestPersistentWorkspaces(AbstractEnrollingBase, ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

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

    enrollment_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

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
        assert_that(res.json_body,
					has_entry('Items', contains(has_entry('alias', 'CLC 3403 - Open'))))
        scope = res.json_body['Items'][0]

        # And we can fetch it by id...
        ntres = self.fetch_by_ntiid(scope['NTIID'])
        # ...and resolve it as a user
        usres = self.resolve_user_response(username=scope['Username'])

        assert_that(ntres.json_body['NTIID'], is_(scope['NTIID']))

        assert_that(usres.json_body['Items'][0]['NTIID'], is_(scope['NTIID']))

    main_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
    section_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice_SubInstances_01'

    def _get_main_and_sect_entries(self, res):
        main_entry, = [
			x for x in res.json_body['Items'] if x['NTIID'] == self.main_ntiid
		]
        sect_entry, = [
			x for x in res.json_body['Items'] if x['NTIID'] == self.section_ntiid
		]
        return main_entry, sect_entry

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_presentation_assets(self):
        # On disk, the main course-instance does not have any
        # presentation assets, so we fallback to the content package.
        # OTOH, section 01 does have its own assets
        res = self.testapp.get(self.all_courses_href)

        assert_that(res.json_body,
					has_entry('Items', has_length(greater_than_or_equal_to(self.expected_workspace_length))))

        main_entry, sect_entry = self._get_main_and_sect_entries(res)

        main_assets = '/sites/platform.ou.edu/CLC3403_LawAndJustice/presentation-assets/shared/v1/'
        sect_assets = '/sites/platform.ou.edu/Courses/Fall2013/CLC3403_LawAndJustice/Sections/01/presentation-assets/shared/v1/'

        assert_that(main_entry,
				    has_entry('PlatformPresentationResources',
                              has_item(has_entry('href', main_assets))))

        assert_that(sect_entry,
                    has_entry('PlatformPresentationResources',
                              has_item(has_entry('href', sect_assets))))

        # If we give the global library a prefix, it manifests here too
        from nti.contentlibrary.interfaces import IContentPackageLibrary
        lib = component.getUtility(IContentPackageLibrary)
        lib.url_prefix = u'content'

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

        assert_that(main_entry,
					has_entry('ContentPackageNTIID',
							  'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))
        assert_that(sect_entry,
					has_entry('ContentPackageNTIID',
							  'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'))

        assert_that(main_entry,
					has_entry('LegacyPurchasableIcon',
							  '/sites/platform.ou.edu/CLC3403_LawAndJustice/images/CLC3403_promo.png'))
        assert_that(sect_entry,
					has_entry('LegacyPurchasableIcon',
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
        assert_that(res.json_body,
					has_entry('Items', has_length(1)))
        enrollment_href = self.require_link_href_with_rel(res.json_body['Items'][0], 'edit')
        self.testapp.get(enrollment_href)

        # and we can see it in the all courses list...
        res = self.testapp.get(self.all_courses_href)
        res = res.json_body
        assert_that(res,
                    has_entry('Items',
						      has_item(has_entries(
                                		'ProviderUniqueID', 'CLC 3403-Restricted',
                                  		'CatalogFamilies', has_entries(
                                                    		'Class', 'CatalogFamilies',
															'Items', has_item(has_entries(
                                                            					'ProviderUniqueID', 'CLC 3403',
                                                            	    			'Class', 'CatalogFamily',
                                                            			     	'Title', 'Law and Justice',
                                                            		 	     	'CatalogFamilyID', not_none(),
                                                            		  	     	'PlatformPresentationResources', not_none())))))))
        assert_that(res,
					has_entry('Items', has_item(has_entry('ProviderUniqueID', 'ENGR 1510-901'))))

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
            principalRoleManager.assignRoleToPrincipal(ROLE_CONTENT_ADMIN.id,
													   'content_admin',
													   check=False)

        res = self.testapp.get('/dataserver2/users/content_admin/Courses/AdministeredCourses',
                               extra_environ=admin_environ)
        # All non-global courses, including our non-public one.
        assert_that(res.json_body, has_entry('Items', has_length(7)))
        for course in res.json_body.get('Items'):
            assert_that(course, has_entry('RoleName', is_(self.editor_role)))

        # Now validate our admin cannot add/update forums, topics and comments.
        course_ext = res.json_body['Items'][0]['CourseInstance']
        discussions = course_ext.get('Discussions')
        self.forbid_link_with_rel(discussions, 'edit')
        self.forbid_link_with_rel(discussions, 'add')

        discussion_contents_rel = self.require_link_href_with_rel(discussions, 'contents')
        discussion_contents = self.testapp.get(discussion_contents_rel,
                                               extra_environ=admin_environ)
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
        for course in res.json_body.get('Items'):
            assert_that(course, has_entry('RoleName', is_(self.editor_role)))

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

        self.testapp.post_json(enroll_href,
                               {'ntiid': self.enrollment_ntiid},
                               extra_environ=environ)
        res = self.testapp.get(enroll_faves, extra_environ=environ)

        assert_that(res.json_body[ITEM_COUNT], is_(1))
        assert_that(res.json_body[TOTAL], is_(1))
        record = res.json_body[ITEMS][0]
        assert_that(record,
                    has_entry('href',
                              is_('%s/%s' % (enroll_href, self.enrollment_ntiid))))

    def _get_catalog_collection(self, name='Courses', environ=None):
        """
        Get the named collection in the `Catalog` workspace in the service doc.
        """
        service_res = self.testapp.get('/dataserver2/service/',
                                       extra_environ=environ)
        service_res = service_res.json_body
        workspaces = service_res['Items']
        catalog_ws = next(x for x in workspaces if x['Title'] == 'Catalog')
        assert_that(catalog_ws, not_none())
        catalog_collections = catalog_ws['Items']
        assert_that(catalog_collections, has_length(2))
        courses_collection = next(
			x for x in catalog_collections if x['Title'] == name
		)
        assert_that(courses_collection, not_none())
        return courses_collection

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_catalog_courses_collection(self):
        """
        Test the courses catalog collection.
        """
        courses_collection = self._get_catalog_collection()
        courses_href = courses_collection['href']
        assert_that(courses_href, not_none())
        available_courses = self.testapp.get(courses_href)
        available_courses = available_courses.json_body
        assert_that(available_courses['Title'], is_('Courses'))
        assert_that(available_courses[ITEMS], has_length(8))
        for item in available_courses[ITEMS]:
            assert_that(item['IsAdmin'], is_(False))
            assert_that(item['IsEnrolled'], is_(False))

        # Filter the collection
        courses_filter_href = '%s?filter=%s' % (courses_href, 'nothing')
        available_courses = self.testapp.get(courses_filter_href).json_body
        assert_that(available_courses[ITEMS], has_length(0))

        courses_filter_href = '%s?filter=%s' % (courses_href, 'clc')
        available_courses = self.testapp.get(courses_filter_href).json_body
        assert_that(available_courses[ITEMS], has_length(3))

        # Paging
        courses_paging_href = '%s?filter=%s&batchStart=%s&batchSize=%s' % (courses_href, 'clc', 0, 1)
        paged_courses = self.testapp.get(courses_paging_href).json_body
        assert_that(paged_courses[ITEMS], has_length(1))

        courses_paging_href = '%s?filter=%s&batchStart=%s&batchSize=%s' % (courses_href, 'clc', 1, 2)
        paged_courses = self.testapp.get(courses_paging_href).json_body
        assert_that(paged_courses[ITEMS], has_length(2))

        # Now fetch popular items
        popular_href = self.require_link_href_with_rel(courses_collection,
                                                       VIEW_CATALOG_POPULAR)
        popular_res = self.testapp.get(popular_href)
        popular_res = popular_res.json_body
        assert_that(popular_res[ITEMS], has_length(3))
        popular_res = self.testapp.get(popular_href, params={'count': 1})
        popular_res = popular_res.json_body
        assert_that(popular_res[ITEMS], has_length(1))

        # More than half the collection 404s
        self.testapp.get(popular_href, params={'count': 5}, status=404)

        popular_res = self.testapp.get(popular_href,
                                       params={'batchStart': 0,
                                               'batchSize': 1})
        popular_res = popular_res.json_body
        assert_that(popular_res[ITEMS], has_length(1))

        # No upcoming courses
        featured_href = self.require_link_href_with_rel(courses_collection,
                                                        VIEW_CATALOG_FEATURED)
        self.testapp.get(featured_href, status=404)

        # Add tags to a entry and filter on tags.
        # Tags are de-dupated on update.
        entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
        child1_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice_SubInstances_01'
        child2_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice_SubInstances_02_Restricted'
        all_ntiids = (entry_ntiid, child1_ntiid, child2_ntiid)
        entry = self.testapp.put_json(self.expected_catalog_entry_href,
                                      {"tags": ('LAW', 'law', '.hidden')})
        entry = entry.json_body
        assert_that(entry,
					has_entry('tags', contains_inanyorder('law', '.hidden')))

        tagged_courses = self.testapp.get('%s?tag=%s' % (courses_href, 'law'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(3))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids, contains_inanyorder(*all_ntiids))

        tagged_courses = self.testapp.get('%s?tag=%s' % (courses_href, '.hidden'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(3))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids, contains_inanyorder(*all_ntiids))

        tagged_courses = self.testapp.get('%s?filter=%s' % (courses_href, 'law'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(3))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids, contains_inanyorder(*all_ntiids))

        # Now set child tag
        child_entry_href = '/dataserver2/Objects/%s' % child2_ntiid
        entry = self.testapp.get(child_entry_href).json_body
        assert_that(entry, has_entry('tags',
                                     contains_inanyorder('law', '.hidden')))

        entry = self.testapp.put_json(child_entry_href,
                                      {"tags": ('child tag',)})
        entry = entry.json_body
        assert_that(entry, has_entry('tags', contains('child tag')))

        tagged_courses = self.testapp.get('%s?tag=%s' % (courses_href, 'law'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(2))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids,
					contains_inanyorder(entry_ntiid, child1_ntiid))

        tagged_courses = self.testapp.get('%s?tag=%s' % (courses_href, '.hidden'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(2))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids,
					contains_inanyorder(entry_ntiid, child1_ntiid))

        tagged_courses = self.testapp.get('%s?tag=%s' % (courses_href, 'child tag'))
        tagged_courses = tagged_courses.json_body
        assert_that(tagged_courses[ITEMS], has_length(1))
        tagged_ntiids = [x['NTIID'] for x in tagged_courses[ITEMS]]
        assert_that(tagged_ntiids, contains(child2_ntiid))

        # By tag view, ordered by most entries in tag
        # Other has 5 entries; child tag  only has one item
        by_tag_href = self.require_link_href_with_rel(courses_collection,
                                                      VIEW_COURSE_BY_TAG)
        by_tag_res = self.testapp.get(by_tag_href).json_body
        by_tag_items = by_tag_res[ITEMS]
        assert_that(by_tag_items, has_length(4))
        by_tag_item_names = [x['Name'] for x in by_tag_items]
        assert_that(by_tag_item_names,
					contains('.hidden', '.nti_other', 'child tag', 'law'))

        child_items = by_tag_items[2]
        assert_that(child_items['Name'], is_('child tag'))
        assert_that(child_items[ITEMS], has_length(1))

        no_tag_items = by_tag_items[1]
        assert_that(no_tag_items['Name'], is_('.nti_other'))
        assert_that(no_tag_items[ITEMS], has_length(5))

        # Exclude hidden, bucket size of 1
        by_tag_res = self.testapp.get(by_tag_href,
                                      params={'hidden_tags': 'false',
											  'bucket_size': 1})
        by_tag_res = by_tag_res.json_body
        by_tag_items = by_tag_res[ITEMS]
        assert_that(by_tag_items, has_length(3))
        item_zero = by_tag_items[0]
        assert_that(item_zero['Name'], is_('.nti_other'))
        for tag_items in by_tag_items:
            assert_that(tag_items[ITEMS], has_length(1))
        by_tag_item_names = [x['Name'] for x in by_tag_items]
        assert_that(by_tag_item_names,
					contains('.nti_other', 'child tag', 'law'))

        # Empty due to bucket limits
        by_tag_res = self.testapp.get(by_tag_href,
                                      params={'bucket_size': 10})
        by_tag_res = by_tag_res.json_body
        by_tag_items = by_tag_res[ITEMS]
        # We have tags and counts, just not to our requested bucket size.
        assert_that(by_tag_items, has_length(4))
        for tag_items in by_tag_items:
            assert_that(tag_items[ITEMS], has_length(0))
            assert_that(tag_items[TOTAL], is_not(0))

        # Drill down into a tag
        by_tag_res = self.testapp.get('%s/%s' % (by_tag_href, 'no_tag_found'))
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res['Name'], is_('no_tag_found'))
        assert_that(by_tag_res[ITEMS], has_length(0))

        by_tag_res = self.testapp.get('%s/%s' % (by_tag_href, 'law'))
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res['Name'], is_('law'))
        assert_that(by_tag_res[ITEMS], has_length(2))

        by_tag_res = self.testapp.get('%s/%s' % (by_tag_href, 'child tag'))
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res[ITEMS], has_length(1))
        assert_that(by_tag_res['Name'], is_('child tag'))

        # Can drill down into our pseudo-tag
        by_tag_res = self.testapp.get('%s/%s' % (by_tag_href, '.nti_other'))
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res[ITEMS], has_length(5))
        assert_that(by_tag_res['Name'], is_('.nti_other'))

        #tags with slashes work if properly encoded
        entry = self.testapp.put_json(child_entry_href,
                                      {"tags": ('some/heirachry',)})
        href = '%s/%s' % (by_tag_href, 'some%2Fheirachry')
        by_tag_res = self.testapp.get(href, extra_environ={'RAW_URI': str(href)})
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res['Name'], is_('some/heirachry'))
        assert_that(by_tag_res[ITEMS], has_length(1))

        # Paging in drilldown
        by_tag_res = self.testapp.get('%s/%s' % (by_tag_href, '.nti_other'),
                                      params={'batchStart':0, 'batchSize':1})
        by_tag_res = by_tag_res.json_body
        assert_that(by_tag_res[ITEMS], has_length(1))
        assert_that(by_tag_res['Name'], is_('.nti_other'))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    @fudge.patch('nti.app.products.courseware.views.catalog_views.PopularCoursesView._include_filter')
    def test_catalog_courses_collection_popular_with_no_results(self, mock_include_filter):
        """
        Test the courses catalog collection. Mocking that no courses are
        available.
        """
        mock_include_filter.is_callable().returns(False)
        courses_collection = self._get_catalog_collection()

        # Now fetch popular
        popular_href = self.require_link_href_with_rel(courses_collection,
                                                       VIEW_CATALOG_POPULAR)
        self.testapp.get(popular_href, status=404)
        self.testapp.get(popular_href, params={'count': 1}, status=404)

    @WithSharedApplicationMockDS(users=True, testapp=True)
    @fudge.patch('nti.app.products.courseware.views.catalog_views.FeaturedCoursesView._include_filter')
    def test_catalog_courses_collection_featured_with_results(self, mock_include_filter):
        """
        Test the courses catalog collection featured view. All courses are
        considered upcoming in this test (and thus in the featured returns).
        """
        mock_include_filter.is_callable().returns(True)
        courses_collection = self._get_catalog_collection()

        # Now fetch featured
        featured_href = self.require_link_href_with_rel(courses_collection,
                                                        VIEW_CATALOG_FEATURED)
        featured_res = self.testapp.get(featured_href)
        featured_res = featured_res.json_body
        featured_items = featured_res[ITEMS]
        assert_that(featured_items, has_length(3))
        assert_that({x['StartDate'] for x in featured_items},
                    contains('2013-08-13T06:00:00Z'))

        featured_res = self.testapp.get(featured_href, params={'count': 1})
        featured_res = featured_res.json_body
        featured_items = featured_res[ITEMS]
        assert_that(featured_items, has_length(1))
        assert_that({x['StartDate'] for x in featured_items},
                    contains('2013-08-13T06:00:00Z'))
        self.testapp.get(featured_href, params={'count': 5}, status=404)

        # Batching
        featured_res = self.testapp.get(featured_href,
                                        params={'batchStart': 0,
                                                'batchSize': 1})
        featured_res = featured_res.json_body
        featured_items = featured_res[ITEMS]
        assert_that(featured_items, has_length(1))

    @WithSharedApplicationMockDS(users=('test_student',), testapp=True)
    def test_catalog_collection_purchased_with_results(self):
        """
        Test the catalog collection purchased collection. Any enrollment record
        is considered 'purchased'.
        """
        student_env = self._make_extra_environ('test_student')
        purchased_collection = self._get_catalog_collection(name='Purchased',
                                                            environ=student_env)
        purchased_href = purchased_collection['href']
        purchased_res = self.testapp.get(purchased_href,
                                         extra_environ=student_env)
        purchased_res = purchased_res.json_body
        purchased_items = purchased_res[ITEMS]
        assert_that(purchased_items, has_length(0))

        enrolled_courses_href = '/dataserver2/users/test_student/Courses/EnrolledCourses'
        enrollment_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
        self.testapp.post_json(enrolled_courses_href,
                               {'ntiid': enrollment_ntiid},
                               status=201,
                               extra_environ=student_env)

        purchased_res = self.testapp.get(purchased_href,
                                         extra_environ=student_env)
        purchased_res = purchased_res.json_body
        purchased_items = purchased_res[ITEMS]
        assert_that(purchased_items, has_length(1))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_windowed_links(self):
        administered_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/AdministeredCourses'
        enrolled_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
        all_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses'
        res = self.testapp.get(administered_path)

        col = res.json_body["Collection"]

        self.require_link_href_with_rel(col, VIEW_ADMINISTERED_WINDOWED)

        res = self.testapp.get(enrolled_path)

        col = res.json_body["Collection"]

        self.require_link_href_with_rel(col, VIEW_ENROLLED_WINDOWED)

        res = self.testapp.get(all_path)

        col = res.json_body["Collection"]

        self.require_link_href_with_rel(col, VIEW_ALL_COURSES_WINDOWED)
        self.require_link_href_with_rel(col, VIEW_ALL_ENTRIES_WINDOWED)
