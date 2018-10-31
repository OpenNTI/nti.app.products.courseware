#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import tempfile
import time

from nti.app.products.courseware.cartridge.cartridge import build_manifest
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
from nti.app.testing.application_webtest import ApplicationLayerTest
from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.tests import mock_dataserver
from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class TestResources(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_resources(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            cartridge = IIMSCommonCartridge(course)
            cartridge_content = cartridge.cartridge_web_content
            from IPython.terminal.debugger import set_trace;set_trace()

            manifest = build_manifest(cartridge)
            vids = [content.export() for content in cartridge_content['videos']]
