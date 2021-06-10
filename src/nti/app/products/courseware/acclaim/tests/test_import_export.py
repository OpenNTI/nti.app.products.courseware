#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import fudge

import shutil
import tempfile

from datetime import datetime

from zope import component

from nti.app.products.acclaim.client_models import AcclaimBadge

from nti.app.products.courseware.acclaim.exporter import AcclaimBadgeExporter

from nti.app.products.courseware.acclaim.importer import AcclaimBadgeImporter

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.cabinet.filer import DirectoryFiler

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.catalog import CourseCatalogFolder

from nti.contenttypes.courses.creator import create_course

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCompletionImportExport(ApplicationLayerTest):
    """
    Validate acclaim badge import/export.
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    def _create_badge(self, template_id, org_id=u'org_id'):
        now = datetime.utcnow()
        result = AcclaimBadge(template_id=template_id,
                              organization_id=org_id,
                              visibility=u'public',
                              public=True,
                              allow_duplicate_badges=False,
                              name=u'badge name',
                              created_at=now,
                              updated_at=now)
        return result

    def _create_source_data(self, source_course):
        badge1 = self._create_badge(u'temp1')
        badge2 = self._create_badge(u'temp2', org_id=u'orgid2')
        container = ICourseAcclaimBadgeContainer(source_course)
        container.get_or_create_badge(badge1)
        container.get_or_create_badge(badge2)

    def _validate_target_data(self, source_course, target_course, copied=True):
        ntiid_copy_check = is_ if copied else is_not
        source_container = ICourseAcclaimBadgeContainer(source_course)
        target_container = ICourseAcclaimBadgeContainer(target_course)

        # Policy container
        assert_that(target_container,
                    has_length(len(source_container)))
        for source_key, target_key in zip(source_container,
                                          target_container):
            assert_that(target_key, ntiid_copy_check(source_key))

        for source_policy, target_policy in zip(source_container.values(),
                                                target_container.values()):
            assert_that(target_policy, is_(source_policy))

    @WithSharedApplicationMockDS(users=False, testapp=True)
    @fudge.patch('nti.contenttypes.courses.creator.library_root')
    def test_import_export(self, mock_library_root):
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            tmp_root_dir = tempfile.mkdtemp(dir="/tmp")
            try:
                # mock root dir
                root = FilesystemBucket(name=u"root")
                root.absolute_path = tmp_root_dir
                mock_library_root.is_callable().returns(root)

                # create course
                catalog = CourseCatalogFolder()
                catalog.__name__ = u'Courses'
                catalog.__parent__ = component.getSiteManager()

                source_course = create_course(u'admin_created', u'course_acclaim', catalog=catalog)
                target_course = create_course(u'admin_imported', u'course_acclaim', catalog=catalog)

                exporter = AcclaimBadgeExporter()
                importer = AcclaimBadgeImporter()

                # 1. empty completion data
                tmp_dir = tempfile.mkdtemp(dir="/tmp")
                export_filer = DirectoryFiler(tmp_dir)
                try:
                    exporter.export(source_course, export_filer, backup=True, salt=1111)
                    export_filer.default_bucket = None
                    importer.process(target_course, export_filer)
                finally:
                    shutil.rmtree(tmp_dir)
                self._validate_target_data(source_course, target_course)

                # 2. with data
                self._create_source_data(source_course)
                tmp_dir = tempfile.mkdtemp(dir="/tmp")
                export_filer = DirectoryFiler(tmp_dir)
                try:
                    exporter.export(source_course, export_filer, backup=True, salt=1111)
                    export_filer.default_bucket = None
                    importer.process(target_course, export_filer)
                finally:
                    shutil.rmtree(tmp_dir)
                self._validate_target_data(source_course, target_course)
            finally:
                shutil.rmtree(tmp_root_dir)
