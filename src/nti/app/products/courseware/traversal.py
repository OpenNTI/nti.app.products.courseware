#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.location.interfaces import LocationError
from zope.traversing.interfaces import ITraversable

from pyramid.interfaces import IRequest

from nti.app.products.courseware.interfaces import ICoursePagesContainerResource

from nti.appserver._adapters import _AbstractExternalFieldTraverser
from nti.appserver._dataserver_pyramid_traversal import _AbstractPageContainerResource

from nti.appserver.interfaces import IExternalFieldTraversable

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.schema.jsonschema import TAG_HIDDEN_IN_UI

from nti.traversal.traversal import ContainerAdapterTraversable

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

@interface.implementer(ICoursePagesContainerResource)
class _CoursePageContainerResource(_AbstractPageContainerResource):
	"""
	A leaf on the traversal tree. Exists to be a named thing that
	we can match view names with. Should be followed by the view name.
	"""

@interface.implementer(ITraversable)
@component.adapter(ICourseInstance, IRequest)
class CoursePagesTraversable(ContainerAdapterTraversable):
	"""	
	Looks for a key in the form Pages(NTIID)/view_name, as a special
	case. Otherwise, looks for named views, or named path adapters if
	no key exists.
	"""

	def traverse(self, key, remaining_path):
		
		# First, try to figure out if our key is in 
		# the form, /Pages(<ntiid>). 

		pfx = 'Pages('
		if key.startswith(pfx) and  key.endswith(')'):
			key = key[len(pfx):-1]
			resource = _CoursePageContainerResource(self, self.request, name=key, parent=self.context)
			if not resource:
				raise LocationError
			return resource
	
		# Otherwise, we look for a named path adapter. 
		return super(CoursePagesTraversable, self).traverse(key, remaining_path)
	