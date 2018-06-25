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

from nti.app.invitations import INVITATIONS

from nti.app.products.courseware import VIEW_ENABLE_INVITATION
from nti.app.products.courseware import SEND_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware import CHECK_COURSE_INVITATIONS_CSV
from nti.app.products.courseware import VIEW_CREATE_COURSE_INVITATION

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.app.products.courseware.utils import has_course_invitations

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.invitations.interfaces import IDisabledInvitation

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInvitationsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and not ILegacyCourseInstance.providedBy(context)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        rels = set()
        if has_permission(ACT_CONTENT_EDIT, context, self.request):
            if has_course_invitations(context):
                rels.add(VIEW_COURSE_ACCESS_TOKENS)
            rels.add(VIEW_CREATE_COURSE_INVITATION)

        if     is_course_instructor(context, self.remoteUser) \
            or is_admin_or_site_admin(self.remoteUser):
            if has_course_invitations(context):
                rels.add(VIEW_COURSE_ACCESS_TOKENS)
            rels.add(SEND_COURSE_INVITATIONS)
            rels.add(CHECK_COURSE_INVITATIONS_CSV)
        elif not rels and not is_enrolled(context, self.remoteUser):
            # If not enrolled in course, user can only accept invites
            rels = (ACCEPT_COURSE_INVITATIONS,)

        for rel in rels:
            link = Link(context, rel=rel, elements=('@@' + rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)

            has_course_invitations(context)


@component.adapter(ICourseInvitation)
@interface.implementer(IExternalMappingDecorator)
class _CourseInvitationDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Allow course invitation objects to be deleted/enabled.
    """

    def _get_course(self, invitation):
        entry = find_object_with_ntiid(invitation.course)
        return ICourseInstance(entry, None)

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and getattr(context, '_p_jar', None) \
           and has_permission(ACT_CONTENT_EDIT, self._get_course(context), self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        ds2 = find_interface(context, IDataserverFolder)
        if not IDisabledInvitation.providedBy(context):
            # Client expects an 'edit' rel here.
            link = Link(ds2,
                        rel='edit',
                        method='DELETE',
                        elements=(INVITATIONS,
                                  context.code,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
        else:
            link = Link(ds2,
                        rel=VIEW_ENABLE_INVITATION,
                        elements=(INVITATIONS,
                                  context.code,
                                  '@@' + VIEW_ENABLE_INVITATION,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
