#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entries
from hamcrest import assert_that

from zope import component

from nti.app.products.courseware.tests import CourseLayerTest

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.webinars.assets import WebinarAsset

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.externalization.externalization import to_external_object

class TestCompletionPolicy(ApplicationLayerTest):

    def test_externalization(self):
        asset = WebinarAsset()
        course = ContentCourseInstance()
        policy = component.queryMultiAdapter((asset, course), ICompletableItemCompletionPolicy)
        assert_that(policy, is_not(none))
        assert_that(to_external_object(policy), has_entries({'Class': 'WebinarAssetCompletionPolicy',
                                                             'offers_completion_certificate': False}))
