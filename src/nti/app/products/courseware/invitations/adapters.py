#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from BTrees.OOBTree import OOSet

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from zope.container.contained import Contained

from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.wref import InvitationWeakRef

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseInvitations)
class CourseInvitations(Contained):

    def __init__(self):
        super(CourseInvitations, self).__init__()
        self._invitation_wrefs = OOSet()

    def add(self, invitation):
        # This is idempotent if the invitation already exists
        container = component.getUtility(IInvitationsContainer)
        container.add(invitation)
        wref = InvitationWeakRef(invitation)
        self._invitation_wrefs.add(wref)
    registerInvitation = append = add

    def remove(self, invitation):
        wref = InvitationWeakRef(invitation)
        try:
            self._invitation_wrefs.remove(wref)
            return True
        except KeyError:
            return False
    removeInvitation = remove

    def get_course_invitations(self):
        result = []
        for wref in self._invitation_wrefs:
            invitation = wref()
            if invitation is not None:
                result.append(invitation)
        return result

    def __len__(self):
        return len(self.get_course_invitations())

ANNOTATION_KEY = u'nti.app.products.courseware.invitations._CourseInvitations'
_CourseInvitations = an_factory( CourseInvitations, ANNOTATION_KEY )

