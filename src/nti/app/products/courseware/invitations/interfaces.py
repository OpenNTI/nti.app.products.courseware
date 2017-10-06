#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.location.interfaces import IContained

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

    def get_course_invitations():
        """
        Returns all course invitations in this container.
        """

    def clear():
        """
        Remove all course invitations in this container.
        """

    def __iter__():
        """
        return an iterable with  all course invitations in this container.
        """

    def __contains__(key):
        """
        check if the specified invitation key is in this container
        """
    
    def __len__(self):
        """
        return the number of invitations in this container
        """
