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

from zope.location.interfaces import ILocation

from nti.app.invitations.interfaces import IUserInvitationsLinkProvider

from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS

from nti.dataserver.interfaces import IUser

from nti.links.links import Link

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser)
@interface.implementer(IUserInvitationsLinkProvider)
class _CourseUserInvitationsLinkProvider(object):

    __slots__ = ('user',)

    def __init__(self, user=None):
        self.user = user

    def links(self, unused_workspace):
        link = Link(self.user,
                    method="POST",
                    rel=ACCEPT_COURSE_INVITATIONS,
                    elements=('@@' + ACCEPT_COURSE_INVITATIONS,))
        link.__name__ = ACCEPT_COURSE_INVITATIONS
        link.__parent__ = self.user
        interface.alsoProvides(link, ILocation)
        return (link,)
