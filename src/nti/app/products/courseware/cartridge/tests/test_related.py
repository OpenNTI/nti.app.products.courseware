#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
does_not = is_not

import shutil
import tempfile

import transaction

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.cartridge.interfaces import IElementHandler
from nti.app.products.courseware.cartridge.interfaces import IBaseElementHandler

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid


class TestRelatedWork(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    local_ref = 'tag:nextthought.com,2011-10:OU-RelatedWorkRef-CS1323_F_2015_Intro_to_Computer_Programming.relatedworkref.relwk:04.02.04_rectangles_versus_triangles'

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_local_content(self):
        # pylint: disable=too-many-function-args
        archive = tempfile.mkdtemp()
        try:
            with mock_dataserver.mock_db_trans(self.ds, 'platform.ou.edu'):
                ref = find_object_with_ntiid(self.local_ref)
                handler = IElementHandler(ref, None)
                assert_that(handler, is_not(none()))
                assert_that(handler, validly_provides(IBaseElementHandler))
                assert_that(handler, verifiably_provides(IBaseElementHandler))
                handler.write_to(archive)
                # cancel
                transaction.doom()
        finally:
            shutil.rmtree(archive, True)
