#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver._util import link_belongs_to_user as link_belongs_to_context

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link


@component.adapter(ICourseInstance)
@interface.implementer(IExternalObjectDecorator)
class _CourseCalendarLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, external):
        return has_permission(ACT_READ, context, self.request)

    def _do_decorate_external(self, context, external):
        _links = external.setdefault(StandardExternalFields.LINKS, [])
        calendar = ICourseCalendar(context, None)
        if calendar is not None:
            _link = Link(calendar,
                         rel='CourseCalendar')
            link_belongs_to_context(_link, context)
            _links.append(_link)


@component.adapter(ICourseCalendar)
@interface.implementer(IExternalMappingDecorator)
class _CourseCalendarDecorator(Singleton):

    def decorateExternalMapping(self, context, result):
        course = ICourseInstance(context, None)
        result['CatalogEntry'] = ICourseCatalogEntry(course, None)


@component.adapter(ICourseCalendarEvent)
@interface.implementer(IExternalMappingDecorator)
class _CourseCalendarEventDecorator(Singleton):

    def decorateExternalMapping(self, context, result):
        course = ICourseInstance(context, None)
        entry = ICourseCatalogEntry(course, None)
        result['CatalogEntryNTIID'] = getattr(entry, 'ntiid', None)


@component.adapter(ICourseCalendar)
@interface.implementer(IExternalObjectDecorator)
class _CourseCalendarEventCreationLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, external):
        return has_permission(ACT_UPDATE, context, self.request)

    def _do_decorate_external(self, context, external):
        _links = external.setdefault(StandardExternalFields.LINKS, [])
        _link = Link(context,
                     rel='create_calendar_event',
                     method='POST')
        link_belongs_to_context(_link, context)
        _links.append(_link)
