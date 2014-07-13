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

import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
	"moved to nti.contenttypes.courses",
	"nti.contenttypes.courses.catalog",
	"CourseCatalog",
	"CourseCatalogInstructorInfo",
	"CourseCatalogEntry")
