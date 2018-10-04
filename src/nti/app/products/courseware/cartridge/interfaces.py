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

from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as TextLine


class IBaseElementHandler(interface.Interface):
    """
    Adapter to handle an asset within a common cartridge
    """

    def iter_items():
        """
        returns an iterable of minidom elements for the manifest items
        """

    def iter_resources():
        """
        returns an iterable of minidom elements for the manifest resources
        """

    def write_to(archive):
        """
        Write the necesary files to the archive
        """


class ICommonCartridge(interface.Interface):
    course = Object(ICourseInstance, title=u"The course")

    archive = TextLine(
        title=u"A valid directory location for the archive data"
    )


class IManifest(interface.Interface):
    """
    Represent a cartrige manifest file
    """
    cartridge = Object(ICommonCartridge, title=u"The cartridge")

    def mark_resource(iden):
        """
        mark a resource in this manifest
        """

    def has_resource(iden):
        """
        check if the resource w/ the specified iden is in this manifest
        """


class IElementHandler(IBaseElementHandler):
    """
    Adapter to handle an asset within a common cartridge
    """
    manifest = Object(IManifest, title=u"The manifest")
