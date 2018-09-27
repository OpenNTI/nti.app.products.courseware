#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

logger = __import__('logging').getLogger(__name__)


def generate_archive(root, archive):
    """
    Generate the archive data for a given item.

    DFS traversal of item structure.
    """
    # Generate XML with placeholder for items if necessary
    xml = root.toXML(archive)
    # Get child items
    items = root.get_items()
    if items:
        # Recursively generate children
        for i in items:
            if not i.traversed:
                child_xml = generate_archive(i, archive)
                xml.insert_child(child_xml)
    # Mark as traversed in case of multiple links
    root.traversed = True
    return xml


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