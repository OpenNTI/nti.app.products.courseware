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
from hamcrest import contains_inanyorder
does_not = is_not

import fudge

import shutil
import tempfile

from zope import component

from nti.app.products.courseware.completion.exporter import CourseCompletionExporter

from nti.app.products.courseware.completion.importer import CourseCompletionImporter

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.cabinet.filer import DirectoryFiler

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.subscribers import completion_context_default_policy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.catalog import CourseCatalogFolder
from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance

from nti.contenttypes.courses.creator import create_course

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCompletionImportExport(ApplicationLayerTest):
    """
    Validate completion import/export.
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    def _create_source_data(self, source_course, optional=[u'ntiid1'], required=[u'ntiid2'], mime_types=()):
        optional_items = []
        for _ntiid in optional:
            optional_items.append(MockCompletableItem(_ntiid))

        required_items = []
        for _ntiid in required:
            required_items.append(MockCompletableItem(_ntiid))

        policy1 = CompletableItemAggregateCompletionPolicy()
        policy2 = CompletableItemAggregateCompletionPolicy()
        policy2.percentage = .25
        policy_container = ICompletionContextCompletionPolicyContainer(source_course)
        policy_container.context_policy = policy1
        policy_container[u'ntiid1'] = policy2

        default_required = ICompletableItemDefaultRequiredPolicy(source_course)
        default_required.add_mime_types(mime_types)

        item_required = ICompletableItemContainer(source_course)
        for item in optional_items:
            item_required.add_optional_item(item)

        for item in required_items:
            item_required.add_required_item(item)

    def _validate_target_data(self, source_course, target_course, copied=True):
        ntiid_copy_check = is_ if copied else is_not
        source_policy_container = ICompletionContextCompletionPolicyContainer(source_course)
        source_default_required = ICompletableItemDefaultRequiredPolicy(source_course)
        source_item_required = ICompletableItemContainer(source_course)

        target_policy_container = ICompletionContextCompletionPolicyContainer(target_course)
        target_default_required = ICompletableItemDefaultRequiredPolicy(target_course)
        target_item_required = ICompletableItemContainer(target_course)

        # Policy container
        assert_that(target_policy_container.context_policy,
                    is_(source_policy_container.context_policy))
        assert_that(target_policy_container,
                    has_length(len(source_policy_container)))
        for source_key, target_key in zip(source_policy_container,
                                                target_policy_container):
            assert_that(target_key, ntiid_copy_check(source_key))

        for source_policy, target_policy in zip(source_policy_container.values(),
                                                target_policy_container.values()):
            assert_that(target_policy, is_(source_policy))

        # Default required mimetypes
        assert_that(target_default_required.mime_types,
                    has_length(len(source_default_required.mime_types)))
        assert_that(target_default_required.mime_types,
                    contains_inanyorder(*source_default_required.mime_types))

        # Item required/optional
        source_required_keys = sorted(source_item_required.get_required_keys())
        target_required_keys = sorted(target_item_required.get_required_keys())
        source_optional_keys = sorted(source_item_required.get_optional_keys())
        target_optional_keys = sorted(target_item_required.get_optional_keys())
        assert_that(target_required_keys,
                    has_length(len(source_required_keys)))
        assert_that(target_optional_keys,
                    has_length(len(source_optional_keys)))

        for source_key, target_key in zip(source_required_keys,
                                          target_required_keys):
            assert_that(target_key, ntiid_copy_check(source_key))

        for source_key, target_key in zip(source_optional_keys,
                                          target_optional_keys):
            assert_that(target_key, ntiid_copy_check(source_key))

    @fudge.patch('nti.contenttypes.completion.internalization.find_object_with_ntiid')
    @WithMockDSTrans
    def test_import_export(self, mock_find_object):
        item1 = MockCompletableItem(u'ntiid1')
        item2 = MockCompletableItem(u'ntiid2')
        # Create course and add to connection
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        export_filer = DirectoryFiler(tmp_dir)
        source_course = ContentCourseInstance()
        target_course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(source_course)
        connection.add(target_course)

        exporter = CourseCompletionExporter()
        importer = CourseCompletionImporter()

        # 1. Empty completion data, backup
        try:
            exporter.export(source_course, export_filer, backup=True, salt=1111)
            importer.process(target_course, export_filer)
        finally:
            shutil.rmtree(tmp_dir)
        self._validate_target_data(source_course, target_course)

        # 2. Empty completion data, no backup
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        export_filer = DirectoryFiler(tmp_dir)
        try:
            exporter.export(source_course, export_filer, backup=False, salt=1111)
            importer.process(target_course, export_filer)
        finally:
            shutil.rmtree(tmp_dir)
        self._validate_target_data(source_course, target_course)

        # 3. Backup with data
        # fake optional/required/policy-container internalization
        fake_find = mock_find_object.is_callable()
        fake_find.returns(item2)
        fake_find.next_call().returns(item1)
        fake_find.next_call().returns(item1)

        self._create_source_data(source_course, mime_types=[u'mimetype1'])
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        export_filer = DirectoryFiler(tmp_dir)
        try:
            exporter.export(source_course, export_filer, backup=True, salt=1111)
            importer.process(target_course, export_filer)
        finally:
            shutil.rmtree(tmp_dir)
        self._validate_target_data(source_course, target_course, copied=True)

        # 4. Backup with data
        fake_find.next_call().returns(item2)
        fake_find.next_call().returns(item1)
        fake_find.next_call().returns(item1)

        target_course = ContentCourseInstance()
        connection.add(target_course)
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        export_filer = DirectoryFiler(tmp_dir)
        try:
            exporter.export(source_course, export_filer, backup=False, salt=1111)
            importer.process(target_course, export_filer)
        finally:
            shutil.rmtree(tmp_dir)
        self._validate_target_data(source_course, target_course)

    def _validate_target_data_with_sections(self, parent_course, section_course, parent_required=[], parent_optional=[], section_required=[], section_optional=[], mime_types=3):
        # Default required mimetypes
        parent_default_required = ICompletableItemDefaultRequiredPolicy(parent_course)
        section_default_required = ICompletableItemDefaultRequiredPolicy(section_course)

        assert_that(parent_default_required.mime_types, has_length(mime_types))
        assert_that(section_default_required.mime_types, has_length(mime_types))

        assert_that(section_default_required.child_policy.mime_types, has_length(0))
        assert_that(section_default_required.parent_policy.mime_types, has_length(mime_types))

        # Item required/optional
        parent_item_required = ICompletableItemContainer(parent_course)
        assert_that(parent_item_required.get_required_keys(), contains_inanyorder(*tuple(parent_required)))
        assert_that(parent_item_required.get_optional_keys(), contains_inanyorder(*tuple(parent_optional)))

        section_item_required = ICompletableItemContainer(section_course)
        assert_that(section_item_required.get_required_keys(), contains_inanyorder(*tuple(section_required)))
        assert_that(section_item_required.get_optional_keys(), contains_inanyorder(*tuple(section_optional)))

        assert_that(section_item_required.parent_container.get_required_keys(), contains_inanyorder(*tuple(parent_item_required.get_required_keys())))
        assert_that(section_item_required.parent_container.get_optional_keys(), contains_inanyorder(*tuple(parent_item_required.get_optional_keys())))

    @WithSharedApplicationMockDS(users=False, testapp=True)
    @fudge.patch('nti.contenttypes.courses.creator.library_root',
                 'nti.contenttypes.completion.internalization.find_object_with_ntiid')
    def test_import_export_with_sections(self, mock_library_root, mock_find_object):
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

                source_course = create_course(u'admin_created', u'course_001', catalog=catalog)
                source_section_course = source_course.SubInstances[u'child1'] = ContentCourseSubInstance()

                target_course = create_course(u'admin_imported', u'course_001', catalog=catalog)
                target_section_course = target_course.SubInstances[u'child1'] = ContentCourseSubInstance()

                exporter = CourseCompletionExporter()
                importer = CourseCompletionImporter()

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
                self._validate_target_data(source_section_course, target_section_course)


                # 2. has completion data
                self._create_source_data(source_course, mime_types=[u'mimetype1'])
                self._create_source_data(source_section_course, optional=[u'ntiid3'], required=['ntiid4'])

                item1 = MockCompletableItem(u'ntiid1')
                item2 = MockCompletableItem(u'ntiid2')

                fake_find = mock_find_object.is_callable()
                fake_find.returns(item2)
                fake_find.next_call().returns(item1)
                fake_find.next_call().returns(item1)

                item3 = MockCompletableItem(u'ntiid3')
                item4 = MockCompletableItem(u'ntiid4')

                fake_find.next_call().returns(item4)
                fake_find.next_call().returns(item3)
                fake_find.next_call().returns(item3)

                tmp_dir = tempfile.mkdtemp(dir="/tmp")
                export_filer = DirectoryFiler(tmp_dir)
                try:
                    exporter.export(source_course, export_filer, backup=True, salt=1111)
                    export_filer.default_bucket = None
                    importer.process(target_course, export_filer)
                finally:
                    shutil.rmtree(tmp_dir)
                self._validate_target_data(source_course, target_course)
                self._validate_target_data(source_section_course, target_section_course)
                self._validate_target_data_with_sections(parent_course=target_course,
                                                         section_course=target_section_course,
                                                         parent_required=['ntiid2'],
                                                         parent_optional=['ntiid1'],
                                                         section_required=['ntiid2', 'ntiid4'],
                                                         section_optional=['ntiid1', 'ntiid3'],
                                                         mime_types=4)

            finally:
                shutil.rmtree(tmp_root_dir)
