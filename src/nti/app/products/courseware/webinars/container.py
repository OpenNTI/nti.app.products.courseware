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

from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)

WEBINAR_CONTAINER_KEY = 'nti.app.products.courseware.webinars.CourseWebinarContainer'


@interface.implementer(ICourseWebinarContainer)
class CourseWebinarContainer(CaseInsensitiveCheckingLastModifiedBTreeContainer,
                             SchemaConfigured):
    createDirectFieldProperties(ICourseWebinarContainer)

    __parent__ = None

    def get_or_create_webinar(self, webinar):
        if webinar.__name__ not in self:
            self[webinar.__name__] = webinar
            webinar.__parent__ = self
        return self[webinar.__name__]


def course_to_webinar_container(course):
    annotations = IAnnotations(course)
    result = annotations.get(WEBINAR_CONTAINER_KEY)
    if result is None:
        result = CourseWebinarContainer()
        result.__parent__ = course
        result.__name__ = WEBINAR_CONTAINER_KEY
        annotations[WEBINAR_CONTAINER_KEY] = result
        IConnection(result).add(result)
    return result
