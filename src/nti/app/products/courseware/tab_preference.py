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

from nti.dataserver.authorization import is_admin

@interface.implementer(ICourseTabConfigurationUtility)
class DefaultCourseTabConfigurationUtility(object):

	def can_edit_tabs(self, user, course):
		return is_admin(user)
