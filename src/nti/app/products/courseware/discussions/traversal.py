#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from pyramid.interfaces import IRequest

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import ContainerAdapterTraversable

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IRequest)
def _discussions_for_course_path_adapter(course, unused_request):
    return ICourseDiscussions(course)


@component.adapter(ICourseDiscussions, IRequest)
class _CourseDiscussionsTraversable(ContainerAdapterTraversable):

    def traverse(self, key, remaining_path):
        return super(_CourseDiscussionsTraversable, self).traverse(key, remaining_path)
