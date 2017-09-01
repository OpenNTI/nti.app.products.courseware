#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware.views import VIEW_LESSONS_CONTAINERS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.contentunit import ContentPackage

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

CS1323_PACKAGE = 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming'


class TestContainerViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_content_containers(self):
        res = self.testapp.get('/dataserver2/Objects/%s' % CS1323_PACKAGE,
                               headers={'Accept': str(ContentPackage.mime_type)})
        res = res.json_body
        # XXX: We do not allow lesson sharing on content-backed units currently.
#         assert_that( res.get(u'LessonContainerCount'), is_(0))
#         lessons_link = self.require_link_href_with_rel(res, VIEW_LESSONS_CONTAINERS)
#         res = self.testapp.get(lessons_link)
#         res = res.json_body
#         assert_that(res, has_entry(ITEMS, has_length(0)))
#         assert_that(res, has_entry(ITEM_COUNT, is_(0)))

