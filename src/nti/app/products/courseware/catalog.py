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

from . import interfaces

from nti.utils.schema import PermissiveSchemaConfigured as SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from nti.utils.property import alias

@interface.implementer(interfaces.ICourseCatalog)
class CourseCatalog(object):

	def __init__( self ):
		self._entries = list()

	# This is all provisional API, not part of the interface
	def addCatalogEntry(self,entry):
		self._entries.append( entry )
		entry.__parent__ = self
		lifecycleevent.added( entry )

	append = addCatalogEntry

	def __len__( self ):
		return len(self._entries)

	def __bool__(self):
		return True
	__nonzero__ = __bool__

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
