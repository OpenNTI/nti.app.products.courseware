#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset
from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_webinars(course, unused_request):
    return ICourseWebinarContainer(course)


@interface.implementer(ICourseInstance)
@component.adapter(IWebinarAsset)
def asset_to_course(asset):
    return find_interface(asset, ICourseInstance, strict=False)
