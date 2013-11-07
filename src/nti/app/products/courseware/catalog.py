#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of course catalogs.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope import lifecycleevent
from zope.container.contained import Contained

from . import interfaces
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.utils.schema import PermissiveSchemaConfigured as SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from nti.utils.property import alias

from nti.dataserver.links import Link

@interface.implementer(interfaces.ICourseCatalog)
class CourseCatalog(Contained):

	lastModified = 0

	def __init__( self ):
		self._entries = list()

	# This is all provisional API, not part of the interface

	__name__ = 'CourseCatalog'

	def addCatalogEntry(self,entry):
		self._entries.append( entry )
		entry.__parent__ = self
		self.lastModified = max( self.lastModified, entry.lastModified )
		lifecycleevent.added( entry )

	append = addCatalogEntry

	def __len__( self ):
		return len(self._entries)

	def __bool__(self):
		return True
	__nonzero__ = __bool__

	def __iter__(self):
		return iter(self._entries)

	def __getitem__(self,ix):
		return self._entries[ix]

@interface.implementer(interfaces.ICourseCatalogInstructorInfo)
class CourseCatalogInstructorInfo(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogInstructorInfo)

	def __repr__(self):
		return "%s(%r)" % (self.__class__.__name__, self.__dict__)

@interface.implementer(interfaces.ICourseCatalogEntry)
class CourseCatalogEntry(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogEntry)

	__name__ = alias('ProviderUniqueID') # This is probably wrong
	__parent__ = None
	def __repr__(self):
		return "%s(%r)" % (self.__class__.__name__, self.__dict__)


	@property
	def links(self):
		return self._make_links()

	def _make_links(self):
		"""
		Subclasses can extend this to customize the available links.

		If we are adaptable to a :class:`.ICourseInstance`, we
		produce a link to that.
		"""
		result = []
		instance = ICourseInstance(self, None)
		if instance:
			result.append( Link( instance, rel="CourseInstance" ) )

		return result


from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.singleton import SingletonDecorator

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseInstance)
class _CourseInstanceLinkDecorator(object):
	"""
	If a course instance can find its catalog entry, return that as a link.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping( self, context, result ):
		# We have no way to know what order these will be
		# called in, so we must preserve anything that exists
		orig_links = result.get( StandardExternalFields.LINKS, () )
		entry = interfaces.ICourseCatalogEntry(context, None)
		_links = None
		if entry:
			_links = [ Link( entry, rel="CourseCatalogEntry" ) ]

		if _links:
			_links.extend( orig_links )
			result[StandardExternalFields.LINKS] = _links
