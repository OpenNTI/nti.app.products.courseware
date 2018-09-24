#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

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
