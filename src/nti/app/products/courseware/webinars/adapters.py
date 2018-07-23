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

from nti.app.authentication import get_remote_user

from nti.app.products.integration.interfaces import IIntegrationCollection

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_integration_collection(course, request):
    """
    Set the :class:`IIntegrationCollection` lineage as our course so
    that we can permission integration objects based on course permission.
    """
    user = get_remote_user(request)
    collection = IIntegrationCollection(user, None)
    if collection is not None:
        collection.__parent__ = course
        return collection


@interface.implementer(ICourseInstance)
@component.adapter(IWebinarAsset)
def asset_to_course(asset):
    return find_interface(asset, ICourseInstance)
