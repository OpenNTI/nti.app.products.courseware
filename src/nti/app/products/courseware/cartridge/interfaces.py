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


class IIMSResource(interface.Interface):
    pass


class IIMSAssociatedContent(interface.Interface):

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


class IIMSWebContentUnit(IIMSResource):
    """
    One unit of web content. May be referenced to compose a Learning Application Object as associated content
    """

    identifier = Int(title=u'Identifier',
                     description=u'The identifier for this web content object within'
                                 u' the common cartridge',
                     required=True)

    dependencies = Dict(key_type=TextLine(),
                        value_type=List(value_type=Object(IIMSResource)))  # TODO doc

    def export():
        """
        Exports this content unit into its Common Cartridge format and returns an open file descriptor.
        The caller of this function is responsible for closing the file and any clean up
        """


class IIMSWebLink(IIMSResource):

    title = TextLine(title=u'Title',
                     description=u'The title of this web link.',
                     required=True)

    url = HTTPURL(title=u'Web Link URL',
                  description=u'The URL which this web link represents.',
                  required=True)

    target = TextLine(title=u'The url target',
                      description=u'Any valid value for the HTML <a> tag target attribute.',
                      required=True,
                      default=u'_self')

    windowFeatures = TextLine(title=u'Javascript window features',
                              description=u'An optional string that can be used as the default parameter'
                                          u' for the standard javascript window open function.',
                              required=False)


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
                                 value_type=List(value_type=Object(IIMSWebContentUnit)),
                                 title=u'IMS Cartridge Web Content',
                                 description=u'IMS Web Content that is globally accessible from other resources.'
                                             u'Objects exported in this field will be imported as global resources'
                                             u'in the destination LMS. The key value in this dict represents the'
                                             u'directory name this content will be in upon export.',
                                 required=True)

    learning_application_objects = List(value_type=Object(IIMSLearningApplicationObject))  #TODO doc
