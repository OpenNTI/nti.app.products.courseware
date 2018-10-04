#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.products.courseware.cartridge.interfaces import IManifest
from nti.app.products.courseware.cartridge.interfaces import IElementHandler
from nti.app.products.courseware.cartridge.interfaces import ICommonCartridge

from nti.base._compat import text_

from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICommonCartridge)
class CommonCartridge(object):

    def __init__(self, course, archive=None):
        self.course = course
        self.archive = archive


@interface.implementer(IManifest)
class Manifest(object):

    def __init__(self, cartridge):
        self.cartridge = cartridge
        self.resources = set()

    @property
    def course(self):
        return getattr(self.cartridge, 'course', None)

    @property
    def archive(self):
        return getattr(self.cartridge, 'archive', None)

    def mark_resource(self, iden):
        if iden is not None:
            self.resources.add(text_(iden))
    mark = mark_resource

    def has_resource(self, iden):
        return text_(iden) in self.resources
    __contains__ = has_resource
    
    def handler(self, context):
        result = IElementHandler(context, None)
        result.manifest = self
        return result
    handler_factory = handler

    def write_to(self, handler):
        archive = getattr(self.cartridge, 'archive', None)
        handler.write_to(archive)
