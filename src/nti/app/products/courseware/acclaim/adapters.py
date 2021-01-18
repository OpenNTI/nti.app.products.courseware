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

from nti.appserver.pyramid_authorization import has_permission

from nti.app.products.integration.workspaces import IntegrationCollection

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_integration_collection(course, request):
    """
    Set the :class:`IIntegrationCollection` lineage as our course so
    that we can permission integration objects based on course permission.
    """
    if has_permission(ACT_CONTENT_EDIT, course, request):
        collection = IntegrationCollection(course)
        collection.__parent__ = course
        return collection


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_badges(course, unused_request):
    return ICourseAcclaimBadgeContainer(course)
