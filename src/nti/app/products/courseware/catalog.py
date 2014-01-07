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
from zope import lifecycleevent
from zope.container.contained import Contained

from . import interfaces
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.utils.schema import PermissiveSchemaConfigured as SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from nti.utils.property import alias

from nti.dataserver.links import Link
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.authorization import ACT_READ
from nti.utils.property import LazyOnClass
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing

from nti.externalization.externalization import make_repr

@interface.implementer(interfaces.ICourseCatalog)
class CourseCatalog(Contained):

	lastModified = 0

	def __init__( self ):
		self._entries = list()

	# This is all provisional API, not part of the interface

	__name__ = 'CourseCatalog'

	@LazyOnClass
	def __acl__( self ):
		# Got to be here after the components are registered
		return acl_from_aces(
			# Everyone logged in has read and search access to the catalog
			ace_allowing( AUTHENTICATED_GROUP_NAME, ACT_READ, CourseCatalog ) )


	def addCatalogEntry(self, entry, event=True):
		"""
		Adds an entry to this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object added event.
		"""
		if entry in self._entries:
			if entry.__parent__ is self:
				return
			raise ValueError("Adding duplicate entry %s", entry)
		self._entries.append( entry )
		entry.__parent__ = self
		self.lastModified = max( self.lastModified, entry.lastModified )
		if event:
			lifecycleevent.added( entry )

	append = addCatalogEntry

	def removeCatalogEntry(self, entry, event=True):
		"""
		Remove an entry from this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object removed event.
		"""
		self._entries.remove(entry)
		if event:
			lifecycleevent.removed(entry)

	def __len__( self ):
		return len(self._entries)

	def __bool__(self):
		return True
	__nonzero__ = __bool__

	def __iter__(self):
		return iter(self._entries)

	def __getitem__(self,ix):
		try:
			return self._entries[ix]
		except TypeError:
			# Ok, is it asking by name, during traversal?
			# TODO: This will need to be cleaned up when/if
			# we have multiple providers and potentially overlapping
			# names...not to mention different semesters
			for entry in self._entries:
				if entry.__name__ == ix:
					return entry
			raise KeyError(ix)

	def __reduce__(self): # Not persistent!
		raise TypeError()


@interface.implementer(interfaces.ICourseCatalogInstructorInfo)
class CourseCatalogInstructorInfo(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogInstructorInfo)

	__repr__ = make_repr()

	def __reduce__(self): # Not persistent!
		raise TypeError()


@interface.implementer(interfaces.ICourseCatalogEntry)
class CourseCatalogEntry(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogEntry)

	__name__ = alias('ProviderUniqueID') # This is probably wrong
	__parent__ = None

	__repr__ = make_repr()

	def __eq__(self, other):
		try:
			# NOTE: This is not very good until we have a better notion of 'provider'
			return self is other or self.ProviderUniqueID == other.ProviderUniqueID
		except AttributeError:
			return NotImplemented

	def __reduce__(self): # Not persistent!
		raise TypeError()

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
