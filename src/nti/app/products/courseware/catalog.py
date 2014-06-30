#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of course catalogs.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from functools import total_ordering

from zope import interface

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.links import Link
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME
from nti.dataserver.containers import CheckingLastModifiedBTreeContainer

from nti.externalization.persistence import NoPickle
from nti.externalization.externalization import WithRepr

from nti.schema.schema import EqHash
from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import PermissiveSchemaConfigured as SchemaConfigured

from nti.utils.property import alias
from nti.utils.property import LazyOnClass

from . import interfaces

@interface.implementer(interfaces.ICourseCatalog)
@NoPickle
@WithRepr
class CourseCatalog(CheckingLastModifiedBTreeContainer):

	lastModified = 0
	__name__ = 'CourseCatalog'


	@LazyOnClass
	def __acl__( self ):
		# Got to be here after the components are registered
		return acl_from_aces(
			# Everyone logged in has read and search access to the catalog
			ace_allowing(AUTHENTICATED_GROUP_NAME, ACT_READ, CourseCatalog ) )

	def addCatalogEntry(self, entry, event=True):
		"""
		Adds an entry to this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object added event.
		"""
		if not entry.__name__:
			raise ValueError(entry)
		if entry.__name__ in self:
			if entry.__parent__ is self:
				return
			raise ValueError("Adding duplicate entry %s", entry)

		if event:
			self[entry.__name__] = entry
		else:
			self._setitemf(entry.__name__, entry)
			entry.__parent__ = self

		self.lastModified = max( self.lastModified, entry.lastModified )


	append = addCatalogEntry

	def removeCatalogEntry(self, entry, event=True):
		"""
		Remove an entry from this catalog.

		:keyword bool event: If true (the default), we broadcast
			the object removed event.
		"""

		if not event:
			l = self._BTreeContainer__len
			try:
				entry = self._SampleContainer__data[entry.__name__]
				del self._SampleContainer__data[entry.__name__]
				l.change(-1)
				entry.__parent__ = None
			except KeyError:
				pass
		else:
			if entry.__name__ in self:
				del self[entry.__name__]


	def isEmpty(self):
		return len(self) == 0

	def clear(self):
		for i in list(self):
			self.removeCatalogEntry(i, event=False)

	def __bool__(self):
		return True
	__nonzero__ = __bool__

	def __iter__(self):
		return iter(self.values())

	def __contains__(self, ix):
		if CheckingLastModifiedBTreeContainer.__contains__(self, ix):
			return True

		try:
			return self[ix] is not None
		except KeyError:
			return False


	def __getitem__(self,ix):
		try:
			return CheckingLastModifiedBTreeContainer.__getitem__(self, ix)
		except KeyError:
			# Ok, is it asking by name, during traversal?
			# This is a legacy case that shouldn't be hit anymore,
			# except during tests that are hardcoded.
			for entry in self:
				if entry.ProviderUniqueID == ix:
					logger.warning("Using legacy ProviderUniqueID to match %s to %s",
								   ix, entry)
					return entry
			raise KeyError(ix)

@interface.implementer(interfaces.ICourseCatalogInstructorInfo)
@WithRepr
@NoPickle
class CourseCatalogInstructorInfo(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogInstructorInfo)

@interface.implementer(interfaces.ICourseCatalogEntry)
@WithRepr
@NoPickle
@total_ordering
@EqHash('ntiid')
class CourseCatalogEntry(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCatalogEntry)

	__name__ = alias('ntiid')
	__parent__ = None

	def __lt__(self, other):
		return self.ntiid < other.ntiid

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
