#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.courseware.interfaces import ICourseTabConfigurationUtility

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization_acl import has_permission

@interface.implementer(ICourseTabConfigurationUtility)
class DefaultCourseTabConfigurationUtility(object):

	def _allow_access(self, user):
		username = getattr(user, 'username', user)
		return username and username.lower().endswith('@nextthought.com')

	def can_edit_tabs(self, user, course):
		if has_permission(ACT_CONTENT_EDIT, course, user):
			return self._allow_access(user)
		return False
