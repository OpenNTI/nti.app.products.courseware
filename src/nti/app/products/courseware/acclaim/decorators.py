#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.products.acclaim.interfaces import IAcclaimIntegration

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadge

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator
from nti.app.renderers.decorators import AbstractRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.authorization import ACT_DELETE

from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IRequest)
@component.adapter(ICourseCatalogEntry, IRequest)
class _CourseAcclaimBadgesDecorator(AbstractRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        # decorate if the integration is enabled, including for the
        # anonymous user, so that badges that will be awarded on course
        # completion are shown in the anonymous catalog
        return component.queryUtility(IAcclaimIntegration)
    
    # pylint: disable=arguments-differ
    def _do_decorate_external(self, context, result):
        course = ICourseInstance(context)
        _links = result.setdefault(LINKS, [])
        link = Link(course,
                    rel='badges',
                    elements=('badges',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = course
        _links.append(link)


@component.adapter(ICourseAcclaimBadge, IRequest)
class _CourseAcclaimBadgeDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Expose awarded badges for this user and any who can READ this user, which
    is typically everyone.
    """

    def _predicate(self, context, unused_result):
        return  self._is_authenticated \
            and has_permission(ACT_DELETE, context)

    # pylint: disable=arguments-differ
    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    method='DELETE',
                    rel='delete')
        _links.append(link)
