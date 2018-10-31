#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from nti.contenttypes.presentation.interfaces import IItemAssetContainer, INTILessonOverview

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def walk(course):
    nodes = list()
    def _recur_nodes(node):
        for child in node.values():
            nodes.append(child)
            _recur_nodes(child)
    outline = course.Outline
    if outline is not None:
        _recur_nodes(outline)

    result = list()
    def _recur_asset(asset):
        if asset is not None:
            result.append(asset)
            if IItemAssetContainer.providedBy(asset):
                for item in asset.Items or ():
                    _recur_asset(item)
    for node in nodes:
        result.append(node)
        _recur_asset(INTILessonOverview(node, None))

    for item in result:
        yield item
