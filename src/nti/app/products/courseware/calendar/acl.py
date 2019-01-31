#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import ACE_DENY_ALL

from nti.dataserver.interfaces import IACLProvider

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseCalendar)
@interface.implementer(IACLProvider)
class CourseCalendarACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        # See comments in nti.dataserver.authorization_acl:has_permission
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        result = []
        if self.__parent__ is not None:
            result.extend(IACLProvider(self.__parent__).__acl__)

        result.append(ACE_DENY_ALL)
        return result
