#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from ZODB.interfaces import IConnection

from zope import interface

from zope.annotation import IAnnotations

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)

ACCLAIM_BADGE_CONTAINER_KEY = 'nti.app.products.courseware.acclaim.CourseAcclaimBadgeContainer'


@interface.implementer(ICourseAcclaimBadgeContainer)
class CourseAcclaimBadgeContainer(CaseInsensitiveCheckingLastModifiedBTreeContainer,
                                  SchemaConfigured):
    createDirectFieldProperties(ICourseAcclaimBadgeContainer)

    __parent__ = None
    __name__ = "badges"

    def get_or_create_badge(self, badge):
        if badge.__name__ not in self:
            self[badge.__name__] = badge
            badge.__parent__ = self
        return self[badge.__name__]


def course_to_badge_container(course, create=True):
    annotations = IAnnotations(course)
    result = annotations.get(ACCLAIM_BADGE_CONTAINER_KEY)
    if result is None and create:
        result = CourseAcclaimBadgeContainer()
        result.__parent__ = course
        annotations[ACCLAIM_BADGE_CONTAINER_KEY] = result
        # pylint: disable=too-many-function-args
        connection = IConnection(result, None)
        if connection is not None:
            connection.add(result)
    return result
