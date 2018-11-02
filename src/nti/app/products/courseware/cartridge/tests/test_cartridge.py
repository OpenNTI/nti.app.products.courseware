#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from hamcrest import assert_that, contains
from hamcrest import is_

from lxml import etree

from nti.app.products.courseware.cartridge.cartridge import build_manifest_items

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge

from nti.app.products.courseware.cartridge.tests import CommonCartridgeLayerTest

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class TestCartridge(CommonCartridgeLayerTest):

    @WithMockDSTrans
    def test_course_tree(self):
        course = self.test_course

        cartridge = IIMSCommonCartridge(course)
        tree = cartridge.course_tree

        assert_that(tree.obj, is_(course.Outline))
        units = tuple(course.Outline.values())
        assert_that(tree.children_objects, is_(units))

        unit_leaf = tree.get_node_from_object(units[0])
        lessons = tuple(INTILessonOverview(unit) for unit in units[0].values())
        assert_that(unit_leaf.children_objects, is_(lessons))

        lesson_leaf = tree.get_node_from_object(lessons[0])
        overview_groups = tuple(lessons[0].Items)
        assert_that(lesson_leaf.children_objects, is_(overview_groups))

        group_leaf = tree.get_node_from_object(overview_groups[0])
        refs = tuple(overview_groups[0].Items)
        assert_that(group_leaf.children_objects, is_(refs))

        media_leaf = tree.get_node_from_object(refs[0])
        assert_that(media_leaf.children_objects, is_(tuple()))

    @WithMockDSTrans
    def test_manifest(self):
        course = self.test_course
        cartridge = IIMSCommonCartridge(course)
        xml_tree = build_manifest_items(cartridge)
        root = etree.fromstring(xml_tree)
        assert_that(root.items(), contains(('identifier', 'NextThought'),
                                           ('structure', 'rooted-hierarchy')))

