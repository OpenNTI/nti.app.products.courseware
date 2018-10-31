#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that

from nti.app.products.courseware.cartridge.tests import CommonCartridgeLayerTest
from nti.contenttypes.presentation.relatedwork import NTIRelatedWorkRef
from nti.dataserver.tests.mock_dataserver import WithMockDS

does_not = is_not
import tempfile


class TestRelatedWork(CommonCartridgeLayerTest):

    @WithMockDS
    def test_local_resource(self):
        rw = NTIRelatedWorkRef()
        resource = tempfile.NamedTemporaryFile()
        resource.name = 'test.docx'
