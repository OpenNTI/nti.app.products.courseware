#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.app.products.courseware.invitations.model import PersistentCourseInvitation

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

logger = __import__('logging').getLogger(__name__)


def create_course_invitation(course, scope=ES_PUBLIC, is_generic=False, code=None):
    """
    Create a :class:`ICourseInvitation` and store it. The `code` will be
    auto-generated if it does not exist.

    :raises: DuplicateInvitationCodeError
    """
    invitation = PersistentCourseInvitation()
    invitation.scope = scope
    entry = ICourseCatalogEntry(course)
    invitation.course = entry.ntiid
    invitation.IsGeneric = is_generic
    if code is not None:
        invitation.code = code
    course_invitations = ICourseInvitations(course)
    # This will autogenerate a code if none exists.
    course_invitations.add(invitation)
    return invitation

