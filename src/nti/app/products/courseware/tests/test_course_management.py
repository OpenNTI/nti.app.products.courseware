#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import assert_that
from hamcrest import contains_inanyorder
does_not = is_not

import shutil

from zope import component

from nti.app.products.courseware import VIEW_COURSE_ADMIN_LEVELS

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.dataserver.tests import mock_dataserver

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestCourseManagement(ApplicationLayerTest):
    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = b'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def tearDown(self):
        """
        Our janux.ou.edu site should have no courses in it.
        """
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            shutil.rmtree(enumeration.root.absolute_path, True)

    def _sync(self):
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            course_catalog = component.getUtility(ICourseCatalog)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            enumeration_root = enumeration.root
            courses_bucket = enumeration_root.getChildNamed(course_catalog.__name__)
            synchronize_catalog_from_root(course_catalog, courses_bucket)

    def _get_admin_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(x for x in workspaces if x['Title'] == 'Courses')
        admin_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMIN_LEVELS)
        return admin_href

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_views(self):
        """
        Validate basic admin level management.
        """
        admin_href = self._get_admin_href()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        # Create
        test_admin_key = 'TestAdminKey'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        # Duplicate
        self.testapp.post_json(admin_href, {'key': test_admin_key}, status=422)

        # Delete
        self.testapp.delete(new_admin_href)
        self.testapp.get(new_admin_href, status=404)

        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sync(self):
        """
        Validate syncs and admin levels.
        """
        admin_href = self._get_admin_href()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        # Create
        test_admin_key = 'TestAdminKey'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        # Sync is ok
        self._sync()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        # Remove filesystem path and re-sync; no change.
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            course_catalog = component.getUtility(ICourseCatalog)
            admin_level = course_catalog[test_admin_key]
            shutil.rmtree( admin_level.root.absolute_path, False )

        self._sync()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        # Delete
        self.testapp.delete(new_admin_href)
        self.testapp.get(new_admin_href, status=404)

        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

    @WithSharedApplicationMockDS(testapp=True, users=('non_admin_user',))
    def test_permissions(self):
        """
        Validate non-admin access.
        """
        environ = self._make_extra_environ('non_admin_user')
        service_res = self.testapp.get('/dataserver2', extra_environ=environ)
        workspaces = service_res.json_body['Items']
        courses_workspace = next(x for x in workspaces if x['Title'] == 'Courses')
        self.forbid_link_with_rel(courses_workspace, VIEW_COURSE_ADMIN_LEVELS)
        course_href = '/dataserver2/++etc++hostsites/janux.ou.edu/++etc++site/Courses'
        admin_href = '%s/@@%s' % (course_href, VIEW_COURSE_ADMIN_LEVELS)
        self.testapp.get(admin_href, extra_environ=environ, status=403)
        self.testapp.post_json(admin_href, {'key': 'TestAdminKey'},
                               extra_environ=environ, status=403)
        course_href = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses'
        self.testapp.delete('%s/%s' % (course_href, 'Fall2013'),
                            extra_environ=environ, status=403)