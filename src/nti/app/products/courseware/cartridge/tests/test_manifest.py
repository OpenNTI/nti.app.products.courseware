#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import shutil
import tempfile

from nti.app.products.courseware.cartridge.generate import walk
from nti.app.products.courseware.cartridge.model import Manifest, CommonCartridge
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
from nti.app.testing.application_webtest import ApplicationLayerTest
from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.tests import mock_dataserver
from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class TestManifest(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_create_manifest(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            from IPython.terminal.debugger import set_trace;set_trace()
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            archive = tempfile.mkdtemp()
            cartridge = CommonCartridge(course, archive)
            try:
                manifest = cartridge.export()
            finally:
                shutil.rmtree(archive)
