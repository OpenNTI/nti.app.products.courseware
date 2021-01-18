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

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IRequest)
class _CourseAcclaimBadgesDecorator(AbstractAuthenticatedRequestAwareDecorator):

    # pylint: disable=arguments-differ
    def _do_decorate_external(self, course, result):
        _links = result.setdefault(LINKS, [])
        link = Link(course,
                    rel='badges',
                    elements=('badges',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = course
        _links.append(link)
