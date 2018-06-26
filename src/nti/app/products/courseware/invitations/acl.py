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

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.contenttypes.courses.acl import editor_aces_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ACE_DENY_ALL

from nti.dataserver.interfaces import IACLProvider

from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInvitation)
@interface.implementer(IACLProvider)
class CourseInvitationACLProvider(object):
    """
    Admins, content admins and editors should be able to manage course
    invitations.
    """

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        entry_ntiid = self.context.Course
        entry = find_object_with_ntiid(entry_ntiid)
        course = ICourseInstance(entry, None)
        aces = editor_aces_for_course(course, self)
        aces.append(ACE_DENY_ALL)
        result = acl_from_aces(aces)
        return result
