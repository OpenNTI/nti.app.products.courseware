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

from nti.appserver.pyramid_authorization import get_cache_acl
from nti.appserver.pyramid_authorization import get_request_acl_cache

from nti.dataserver.interfaces import ACE_DENY_ALL

from nti.dataserver.interfaces import IACLProvider

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
            acl_cache = get_request_acl_cache()
            acl = get_cache_acl(self.__parent__, acl_cache)
            try:
                result.extend(acl.__acl__)
            except AttributeError:
                pass

        result.append(ACE_DENY_ALL)
        return result
