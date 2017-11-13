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

from nti.app.products.courseware import SEND_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware import CHECK_COURSE_INVITATIONS_CSV

from nti.app.products.courseware.utils import has_course_invitations

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.authorization import is_content_admin
from nti.dataserver.authorization import is_admin_or_site_admin

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInvitationsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and not ILegacyCourseInstance.providedBy(context) \
           and has_course_invitations(context)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        rels = ()
        if     is_course_instructor(context, self.remoteUser) \
            or is_admin_or_site_admin(self.remoteUser):
            rels = (VIEW_COURSE_ACCESS_TOKENS,
                    SEND_COURSE_INVITATIONS,
                    CHECK_COURSE_INVITATIONS_CSV)
        elif is_content_admin(self.remoteUser):
            rels = (VIEW_COURSE_ACCESS_TOKENS,)
        elif not is_enrolled(context, self.remoteUser):
            # If not enrolled in course, user can accept invites
            rels = (ACCEPT_COURSE_INVITATIONS,)

        for rel in rels:
            link = Link(context, rel=rel, elements=('@@' + rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
