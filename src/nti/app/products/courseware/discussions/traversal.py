#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from pyramid.interfaces import IRequest

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import ContainerAdapterTraversable

@component.adapter(ICourseInstance, IRequest)
def _discussions_for_course_path_adapter(course, request):
	return ICourseDiscussions(course)

@component.adapter(ICourseDiscussions, IRequest)
class _CourseDiscussionsTraversable(ContainerAdapterTraversable):

	def traverse(self, key, remaining_path):
		return super(_CourseDiscussionsTraversable, self).traverse(key, remaining_path)
