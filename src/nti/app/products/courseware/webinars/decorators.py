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

from nti.app.products.courseware.webinars.calendar import IWebinarCalendarEvent

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
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


@component.adapter(IWebinarCalendarEvent, IRequest)
class _WebinarEventDecorator(AbstractAuthenticatedRequestAwareDecorator):

    # pylint: disable=arguments-differ
    def _do_decorate_external(self, event, result):
        course = ICourseInstance(event, None)
        if course is None:
            return

        result['WebinarTitle'] = event.webinar.title
        result['WebinarTimes'] = event.webinar.times

        _links = result.setdefault(LINKS, [])
        link = Link(event.webinar,
                    rel='Webinar')
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = course
        _links.append(link)
