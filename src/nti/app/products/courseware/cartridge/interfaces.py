#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope import interface

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.schema.field import Bool
from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as TextLine


class IBaseElementHandler(interface.Interface):
    """
    Adapter to handle an asset within a common cartridge
    """

    def toXML():
        """
        returns the minidom implementation of the manifest element
        """

    def write():
        """
        Write the necesary files to the archive
        """


class IGenerationNode(interface.Interface):
    """
    Base for an item to generate XML
    """

    traversed = Bool(title=u"If this item has been traversed",
                     required=False,
                     default=False)

    handler = Object(IBaseElementHandler, title=u"XML generation handler")

    def get_items():
        """
        Get all sub-items of this node
        """


class ICourseGenerationNode(IGenerationNode, ICourseInstance):
    """
    Implementation of generation logic for a course instance
    """


class ICommonCartridge(interface.Interface):
    course = Object(ICourseGenerationNode, title=u"The course")

    archive = TextLine(
        title=u"A valid directory location for the archive data"
    )


class IManifest(interface.Interface):
    """
    Represent a cartrige manifest file
    """
    cartridge = Object(ICommonCartridge, title=u"The cartridge")


class IManifestBuilder(interface.Interface):
    manifest = Object(IManifest, title=u"The manifest")


class IElementHandler(IBaseElementHandler):
    """
    Adapter to handle an asset within a common cartridge
    """
    manifest = Object(IManifest, title=u"The manifest")
