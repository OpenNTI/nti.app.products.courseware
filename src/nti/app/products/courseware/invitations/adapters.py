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

from zope.annotation.factory import factory as an_factory

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

import BTrees

from nti.app.authentication import get_remote_user

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation
from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.invitation import JoinCourseInvitation

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.wref import InvitationWeakRef

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseInvitations)
class CourseInvitations(Contained):

    family = BTrees.family64

    def __init__(self):
        super(CourseInvitations, self).__init__()
        self._invitation_wrefs = self.family.OO.OOSet()

    @Lazy
    def container(self):
        return component.getUtility(IInvitationsContainer)

    def add(self, invitation):
        # This is idempotent if the invitation already exists
        self.container.add(invitation)
        wref = InvitationWeakRef(invitation)
        self._invitation_wrefs.add(wref)
    registerInvitation = append = add

    def remove(self, invitation, propagate=False):
        wref = InvitationWeakRef(invitation)
        try:
            invitation = wref()
            self._invitation_wrefs.remove(wref)
            if invitation is not None and propagate:
                self.container.remove(invitation)
            return True
        except KeyError:
            return False
    removeInvitation = remove

    def clear(self, propagate=False):
        for wref in list(self._invitation_wrefs):
            self.remove(wref, propagate)

    def get_course_invitations(self):
        result = []
        for wref in self._invitation_wrefs:
            invitation = wref()
            if invitation is not None:
                result.append(invitation)
        return result

    def __iter__(self):
        return iter(self.get_course_invitations())

    def __contains__(self, key):
        container = component.getUtility(IInvitationsContainer)
        invitation = container.get(key)
        return ICourseInvitation.providedBy(invitation) \
           and InvitationWeakRef(invitation) in self._invitation_wrefs

    def __len__(self):
        return len(self.get_course_invitations())


ANNOTATION_KEY = u'nti.app.products.courseware.invitations._CourseInvitations'
_CourseInvitations = an_factory(CourseInvitations, ANNOTATION_KEY)


@component.adapter(ICourseInvitation)
@interface.implementer(IJoinCourseInvitation)
def _create_join_course_invitation(course_invitation):
    """
    If we have a generic course invitation, adapt into a
    :class:`IJoinCourseInvitation` specific to our remote user.
    """
    if course_invitation.IsGeneric:
        user_invitation = JoinCourseInvitation()
        user_invitation.scope = course_invitation.Scope
        user_invitation.course = course_invitation.Course
        user = get_remote_user()
        user_invitation.receiver = getattr(user, 'username', '')
        container = component.getUtility(IInvitationsContainer)
        container.add(user_invitation)
        return user_invitation
