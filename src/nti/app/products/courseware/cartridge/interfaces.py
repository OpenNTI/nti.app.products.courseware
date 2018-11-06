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

from zope.schema import Dict
from zope.schema import List

from nti.schema.field import Int
from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as TextLine

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.common.datastructures import ObjectHierarchyTree


class ICanvasWikiContent(interface.Interface):
    """
    Marker interface for content that should be processed as a Canvas Wiki page
    """


class IIMSResource(interface.Interface):

    identifier = Int(title=u'Identifier',
                     description=u'The identifier for this web content object within'
                                 u' the common cartridge',
                     required=True)

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True)

    def export(path):
        """
        Exports this resource into its Common Cartridge format and writes it into the supplied archive.
        """


class IIMSCommonCartridgeExtension(interface.Interface):
    """
    A subscription interface for common cartridge extensions
    """


class IIMSWebContentUnit(IIMSResource):
    """
    One unit of web content. May be referenced to compose a Learning Application Object as associated content
    Web Content units are responsible for exporting their dependencies
    """



    dependencies = Dict(key_type=TextLine(),
                        value_type=List(value_type=Object(IIMSResource)))  # TODO doc

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True,
                    default='webcontent',
                    readonly=True)


class IIMSWebLink(IIMSResource):

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True,
                    default='imswl_xmlv1p1',
                    readonly=True)


class IIMSDiscussionTopic(IIMSResource):

    dependencies = Dict(key_type=TextLine(),
                        value_type=List(value_type=Object(IIMSResource)))  # TODO doc

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True,
                    default='imsdt_xmlv1p1',
                    readonly=True)


class IIMSAssociatedContent(IIMSResource):

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True,
                    default='associatedcontent/imscc_xmlv1p2/learning-application-resource',
                    readonly=True)


class ICartridgeWebContent(interface.Interface):
    """
    Marker interface for cartridge web content
    """


class IIMSCommonCartridge(interface.Interface):
    # TODO doc

    # errors = List()

    resources = Dict(key_type=Int(),
                     value_type=Object(IIMSResource))

    # course_tree = Object()


class IIMSManifestResources(interface.Interface):
    pass
