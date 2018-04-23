#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import json
import fudge
import shutil
import tempfile

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import greater_than

from nti.app.products.courseware.utils import EXPORT_HASH_KEY
from nti.app.products.courseware.utils import COURSE_META_NAME

from nti.app.products.courseware.utils.exporter import CourseMetaInfoExporter

from nti.cabinet.filer import DirectoryFiler

from nti.cabinet.mixins import get_file_size

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.tests import CourseLayerTest

from nti.externalization.interfaces import StandardExternalFields

CREATOR = StandardExternalFields.CREATOR


class TestExporter(CourseLayerTest):
    
    @fudge.patch('nti.app.products.courseware.utils.exporter.CourseMetaInfoExporter._get_export_hash',
                 'nti.app.products.courseware.utils.exporter.CourseMetaInfoExporter._get_remote_user')
    def test_export_course_meta_info(self, mock_get_export_hash, mock_get_remote_user):
        expected_export_hash = u'export_hash'
        mock_get_export_hash.is_callable().returns(expected_export_hash)
        expected_user = u'Heisenberg'
        mock_get_remote_user.is_callable().returns(expected_user)
        path = os.path.join(os.path.dirname(__file__),
                            'TestSynchronizeWithSubInstances',
                            'Spring2014',
                            'Gateway')
        inst = ContentCourseInstance()
        inst.root = FilesystemBucket(name=u"Gateway")
        inst.root.absolute_path = path
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            exporter = CourseMetaInfoExporter()
            exporter.export(inst, filer)
            path = os.path.join(tmp_dir, COURSE_META_NAME)
            assert_that(os.path.exists(path), is_(True))
            assert_that(get_file_size(path), is_(greater_than(0)))
            export_meta = json.load(filer.get(path))
            export_hash = export_meta[EXPORT_HASH_KEY]
            assert_that(export_hash, is_(expected_export_hash))
            user = export_meta[CREATOR]
            assert_that(user, is_(expected_user))
        finally:
            shutil.rmtree(tmp_dir)
            