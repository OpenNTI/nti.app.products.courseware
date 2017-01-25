#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.location.interfaces import ILocation

from nti.app.products.courseware.resources import RESOURCES

from nti.app.products.courseware.utils import PreviewCourseAccessPredicateDecorator

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import is_enrolled

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS


@interface.implementer(IExternalMappingDecorator)
class _CourseResourcesLinkDecorator(PreviewCourseAccessPredicateDecorator):

    def _predicate(self, context, result):
        user = self.remoteUser
        course = ICourseInstance(context, None)
        # XXX: Unauth access?
        result =  super(_CourseResourcesLinkDecorator, self)._predicate(context, result) \
             and not ILegacyCourseInstance.providedBy(course) \
             and (is_enrolled(context, user) or self.instructor_or_editor)
        return result

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=RESOURCES, elements=(RESOURCES,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)
