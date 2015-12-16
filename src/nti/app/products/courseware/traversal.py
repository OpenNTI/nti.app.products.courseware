#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.interfaces import IRequest
from nti.appserver._adapters import _AbstractExternalFieldTraverser

from nti.appserver.interfaces import IExternalFieldTraversable

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseInstance 
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.schema.jsonschema import TAG_HIDDEN_IN_UI

@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalFieldTraversable)
class _OutlineNodeExternalFieldTraverser(_AbstractExternalFieldTraverser):

	def __init__(self, context, request=None):
		super(_OutlineNodeExternalFieldTraverser, self).__init__(context, request=request)
		allowed_fields = set()
		outline_iface = iface_of_node(context)
		for k, v in outline_iface.namesAndDescriptions(all=True):
			__traceback_info__ = k, v
			if interface.interfaces.IMethod.providedBy(v):
				continue
			# v could be a schema field or an interface.Attribute
			if v.queryTaggedValue(TAG_HIDDEN_IN_UI):
				continue
			allowed_fields.add(k)
		self._allowed_fields = allowed_fields

@component.adapter(ICourseInstance, IRequest)
def _discussions_for_course_path_adapter(course, request):
	return ICourseDiscussions(course)
