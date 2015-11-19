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

from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent

from zope.location.interfaces import ILocation

from zope.security.interfaces import IPrincipal

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.common.property import Lazy

from nti.contentfolder.model import RootFolder

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

from nti.traversal.traversal import find_interface

from .interfaces import ICourseRootFolder

RESOURCES = 'resources'
LINKS = StandardExternalFields.LINKS

@interface.implementer(ICourseRootFolder)
class CourseRootFolder(RootFolder):
	pass

@component.adapter(ICourseInstance)
@interface.implementer(ICourseRootFolder)
def _course_resources(course, create=True):
	result = None
	annotations = IAnnotations(course)
	try:
		KEY = RESOURCES
		result = annotations[KEY]
	except KeyError:
		if create:
			result = CourseRootFolder(name=RESOURCES)
			annotations[KEY] = result
			result.__name__ = KEY
			result.__parent__ = course
	return result

def _resources_for_course_path_adapter(context, request):
	course = ICourseInstance(context)
	return _course_resources(course)

@component.adapter(ICourseInstance, IObjectAddedEvent)
def _on_course_added(course, event):
	_course_resources(course)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, event):
	root = _course_resources(course, False)
	if root is not None:
		root.clear()

@component.adapter(ICourseRootFolder)
@interface.implementer(IACLProvider)
class CourseRootFolderACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		aces = [ ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, self),
				 ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self)) ]

		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is not None:
			# give instructors special powers
			for i in course.instructors or ():
				aces.extend(ace_allowing(i, ALL_PERMISSIONS, type(self))
							for i in course.instructors or ())

			# all scopes have read access
			course.initScopes()
			for scope in course.SharingScopes:
				aces.append(ace_allowing(IPrincipal(scope), ACT_READ, type(self)))

			if ICourseSubInstance.providedBy(course):
				parent = get_parent_course(course)
				for i in parent.instructors or ():
					aces.extend(ace_allowing(i, ACT_READ, type(self))
								for i in course.instructors or ())

		result = acl_from_aces(aces)
		return result

@interface.implementer(IExternalMappingDecorator)
class _CourseResourcesLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		user = self.remoteUser
		return 		bool(self._is_authenticated) \
				and (is_enrolled(context, user) or is_course_instructor(context, user))

	def _do_decorate_external(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel=RESOURCES, elements=(RESOURCES,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)
