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

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseTabConfigurationUtility)
class DefaultCourseTabConfigurationUtility(object):

    def can_edit_tabs(self, user, unused_course=None):
        return is_admin(user)
