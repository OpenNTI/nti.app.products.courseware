#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.presentation.decorators.assets import CONTENT_MIME_TYPE

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit
from nti.app.products.courseware.cartridge.interfaces import IIMSWebLink
from nti.app.products.courseware.cartridge.interfaces import IIMSLearningApplicationObject

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


class IMSWebContentResource(AbstractIMSWebContent):
    """
    pdf, ppt, docx, etc
    """

    @Lazy
    def filename(self):
        return os.path.basename(self.context.href)

    def export(self, path):
        package = find_interface(self.context, IContentPackage, strict=False)
        root = getattr(package, 'root', None)
        if not IFilesystemBucket.providedBy(root):
            logger.warning("Unsupported bucket Boto?")
            raise CommonCartridgeExportException(u"Unable to locate file on disk for %s. Is this resource "
                                                 u"stored on Boto?" % self.context.label)
        elif self.context.href and root:
            source_path = os.path.join(root.absolute_path, self.context.href)
            filename = os.path.basename(source_path)
            target_path = os.path.join(path, filename)
            self.copy_resource(source_path, target_path)
        else:
            raise CommonCartridgeExportException(u"Unable to locate a content package for %s" % self.context.label)


class IMSWebContentNativeReading(AbstractIMSWebContent):
    """
    A content package that is rendered into web content
    """

    def export(self, archive):
        pass


def _related_work_factory(related_work, resource_type=None):
    """
    Parses a related work into an IMS web link if it is an external link,
    a Native Reading Web Content unit if it is a content unit, or
    a Resource Web Content unit if it is a local resource (pdf, etc)
    """
    # Web Links => IMS Web Links
    if related_work.type == 'application/vnd.nextthought.externallink' and\
            bool(urllib_parse.urlparse(related_work.href).scheme) and resource_type == 'IMS Web Link':
        return IMSWebLink(related_work)
    # Resource links => IMS Web Content
    elif related_work.type == 'application/vnd.nextthought.externallink' and\
            related_work.href.startswith('resources/') and resource_type == 'IMS Web Content':
        return IMSWebContentResource(related_work)
    # Native readings => IMS Learning Application Objects
    elif related_work.type == CONTENT_MIME_TYPE and resource_type == 'IMS Learning Application Object':
        return IMSWebContentNativeReading(related_work)
    else:
        return None


@interface.implementer(IIMSWebContentUnit)
@component.adapter(INTIRelatedWorkRef)
def related_work_to_web_content_factory(related_work):
    return _related_work_factory(related_work, resource_type='IMS Web Content')


@interface.implementer(IIMSWebLink)
@component.adapter(INTIRelatedWorkRef)
def related_work_to_web_link_factory(related_work):
    return _related_work_factory(related_work, resource_type='IMS Web Link')


@interface.implementer(IIMSLearningApplicationObject)
@component.adapter(INTIRelatedWorkRef)
def related_work_to_learning_application_object_factory(related_work):
    return _related_work_factory(related_work, resource_type='IMS Learning Application Object')


@interface.implementer(IIMSWebLink)
class IMSWebLink(object):

    def __init__(self, asset):
        self.context = asset
