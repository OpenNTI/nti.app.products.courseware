#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceIntegrationsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Return a link to the integration collections off of our
    course instance.
    """

    def _predicate(self, context, unused_result):
        return has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(Link(context,
                           rel='Integrations',
                           elements=('Integrations',)))
