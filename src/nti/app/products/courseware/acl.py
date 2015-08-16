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

from zope.security.interfaces import IPrincipal

from nti.common.property import Lazy

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from .interfaces import IEnrolledCoursesCollection
from .interfaces import IAdministeredCoursesCollection

@interface.implementer(IACLProvider)
class CollectionACLProviderMixin(object):

	def __init__(self, context):
		self.context = context

	@Lazy
	def __acl__(self):
		user = self.context.__parent__.user
		aces = [ace_allowing(IPrincipal(user),
							 (ALL_PERMISSIONS),
							 CollectionACLProviderMixin)]
		aces.append(ACE_DENY_ALL)
		return acl_from_aces(aces)

@component.adapter(IEnrolledCoursesCollection)
class EnrolledCoursesCollectionACLProvider(CollectionACLProviderMixin):
	pass

@component.adapter(IAdministeredCoursesCollection)
class AdministeredCoursesCollectionACLProvider(CollectionACLProviderMixin):
	pass
