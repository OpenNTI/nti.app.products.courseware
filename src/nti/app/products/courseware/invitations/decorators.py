#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.products.courseware import SEND_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware import CHECK_COURSE_INVITATIONS_CSV

from nti.app.products.courseware.utils import has_course_invitations

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.authorization import ACT_NTI_ADMIN

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInvitationsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, result):
        return self._is_authenticated \
            and not ILegacyCourseInstance.providedBy(context)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        if has_course_invitations(context):
            # instructor or admin, it can send invitations
            if        is_course_instructor(context, self.remoteUser) \
                or has_permission(ACT_NTI_ADMIN, context, self.request):
                for name in (VIEW_COURSE_ACCESS_TOKENS,
                             SEND_COURSE_INVITATIONS,
                             CHECK_COURSE_INVITATIONS_CSV):
                    link = Link(context, rel=name, elements=(name,))
                    interface.alsoProvides(link, ILocation)
                    link.__name__ = ''
                    link.__parent__ = context
                    _links.append(link)
            # if not enrolled in course it can accept invites
            elif not is_enrolled(context, self.remoteUser):
                link = Link(context, rel=ACCEPT_COURSE_INVITATIONS,
                            elements=('@@' + ACCEPT_COURSE_INVITATIONS,))
                interface.alsoProvides(link, ILocation)
                link.__name__ = ''
                link.__parent__ = context
                _links.append(link)
