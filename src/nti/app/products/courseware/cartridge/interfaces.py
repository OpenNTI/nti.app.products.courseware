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

from nti.schema.field import HTTPURL
from nti.schema.field import Int
from nti.schema.field import Object
from nti.schema.field import DecodingValidTextLine as TextLine


class ICanvasWikiContent(interface.Interface):
    """
    Marker interface for content that should be processed as a Canvas Wiki page
    """


class IIMSResource(interface.Interface):

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True)

    def export(path):
        """
        Exports this resource into its Common Cartridge format and writes it into the supplied archive.
        """


class IIMSAssociatedContent(IIMSResource):

    type = TextLine(title=u'Object Type',
                    description=u'The IMS characteristic object type.',
                    required=True,
                    default='associatedcontent/imscc_xmlv1p2/learning-application-resource',
                    readonly=True)


class IIMSLearningApplicationObject(interface.Interface):

    associated_content = List(title=u'Associated Content',
                              description=u'The associated content objects.',
                              required=False,
                              value_type=Object(IIMSAssociatedContent,
                                                title=u'Associated Content Object',
                                                required=True))


class IIMSCommonCartridgeExtension(interface.Interface):
    """
    A subscription interface for common cartridge extensions
    """


class IIMSWebContentUnit(IIMSResource):
    """
    One unit of web content. May be referenced to compose a Learning Application Object as associated content
    Web Content units are responsible for exporting their dependencies
    """

    identifier = Int(title=u'Identifier',
                     description=u'The identifier for this web content object within'
                                 u' the common cartridge',
                     required=True)

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


class ICartridgeWebContent(interface.Interface):
    """
    Marker interface for cartridge web content
    """


class IIMSManifest(interface.Interface):
    """
    Manifest file for a Common Cartridge
    """

    # TODO add fields


class IIMSCommonCartridge(interface.Interface):

    manifest = Object(IIMSManifest,
                      title=u'IMS manifest',
                      required=True)

    cartridge_web_content = Dict(key_type=TextLine(),
                                 value_type=Dict(key_type=TextLine(), value_type=Object(IIMSWebContentUnit)),
                                 title=u'IMS Cartridge Web Content',
                                 description=u'IMS Web Content that is globally accessible from other resources.'
                                             u'Objects exported in this field will be imported as global resources'
                                             u'in the destination LMS. The key value in this dict represents the'
                                             u'directory name this content will be in upon export.',
                                 required=True)

    learning_application_objects = List(value_type=Object(IIMSLearningApplicationObject))  #TODO doc


class IIMSManifestResources(interface.Interface):
    pass
