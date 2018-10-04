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

    def mark_resource(self, iden):
        if iden is not None:
            self.resources.add(text_(iden))
    mark = mark_resource

    def has_resource(self, iden):
        return text_(iden) in self.resources

    def __contains__(self, iden):
        return self.has_resource(iden)