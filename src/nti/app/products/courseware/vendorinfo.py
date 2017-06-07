#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.courseware.interfaces import ICoursePublishableVendorInfo


@interface.implementer(ICoursePublishableVendorInfo)
class _DefaultCoursePublishableVendorInfo(object):

    def __init__(self, context):
        self.context = context

    def info(self):
        return None
