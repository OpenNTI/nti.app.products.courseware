#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Policies and components that are related to courseware.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.appserver.interfaces import IUserCapabilityFilter

from nti.appserver.pyramid_authorization import has_permission

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser

@component.adapter(IUser)
@interface.implementer(IUserCapabilityFilter)
class AdvancedEditingCapabilityFilter(object):
	"""
	Removes the Advanced Editing capability for users that don't have
	global edit permissions.
	"""

	def __init__(self, context=None):
		self.user = context

	def filterCapabilities(self, capabilities):
		result = set(capabilities)
		if self.user is None or not has_permission(nauth.ACT_CONTENT_EDIT, self.user.__parent__):
			result.discard('nti.platform.courseware.advanced_editing')
		return result
