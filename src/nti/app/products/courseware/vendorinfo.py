#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.courseware.interfaces import ICoursePublishableVendorInfo

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICoursePublishableVendorInfo)
class _DefaultCoursePublishableVendorInfo(object):

    __slots__ = ('context',)

    def __init__(self, context):
        self.context = context

    def info(self):
        return None
