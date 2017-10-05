#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.container.interfaces import IContained

from nti.invitations.interfaces import IUnActionableInvitation

from nti.schema.field import Bool
from nti.schema.field import TextLine


class ICourseInvitation(IUnActionableInvitation):

    Scope = TextLine(title=u"The enrollment scope.", required=True)

    Description = TextLine(title=u"The invitation description.",
                           required=True)

    Course = TextLine(title=u"Course catalog entry NTIID.", required=False)
    Course.setTaggedValue('_ext_excluded_out', True)

    IsGeneric = Bool(title=u"Invitation code is generic.",
                     required=False,
                     default=False)
    IsGeneric.setTaggedValue('_ext_excluded_out', True)


class ICourseInvitations(IContained):
    """
    Holds course invitations for a specific :class:``ICourseInstance``
    """

    def add(invitation):
        """
        Registers the given invitation with this object. This object is responsible for
        assigning the invitation code and taking ownership of the invitation.
        """
    registerInvitation = add

    def remove(invitation):
        """
        Remove the given invitation with this object.
        """
    removeInvitation = remove

    def get_course_invitations(self):
        """
        Returns all course invitations in this container.
        """
