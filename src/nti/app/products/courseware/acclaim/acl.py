#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ACL providers for course data.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from nti.app.products.acclaim.authorization import ACT_ACCLAIM

from nti.app.products.courseware.interfaces import ICourseIntegrationCollection

from nti.contenttypes.courses.common import get_course_editors

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ISupplementalACLProvider

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseIntegrationCollection)
@interface.implementer(ISupplementalACLProvider)
class AcclaimBadgesSupplementalACLProvider(object):

    def __init__(self, context):
        self.context = context
        self.course = context.__parent__

    @Lazy
    def __acl__(self):
        result = []
        for editor in get_course_editors(self.course):
            editor = IPrincipal(editor)
            ace = ace_allowing(editor, ACT_ACCLAIM, type(self))
            result.append(ace)
        return acl_from_aces(result)
