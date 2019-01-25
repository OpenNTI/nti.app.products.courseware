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

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.calendar.interfaces import ICalendarEventUIDProvider

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarDynamicEvent
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarDynamicEventProvider

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.app.products.webinar.interfaces import IWebinar

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from nti.externalization.datastructures import InterfaceObjectIO

from nti.ntiids.oids import to_external_ntiid_oid

from nti.schema.field import Object

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.site.site import get_component_hierarchy_names

logger = __import__('logging').getLogger(__name__)


class IWebinarCalendarEvent(ICourseCalendarDynamicEvent):

    webinar = Object(IWebinar, required=True)

    webinar.setTaggedValue('_ext_excluded_out', True)


@interface.implementer(IWebinarCalendarEvent)
class WebinarCalendarEvent(CourseCalendarEvent):

    __external_can_create__ = False

    __external_class_name__ = "WebinarCalendarEvent"

    mimeType = mime_type = "application/vnd.nextthought.webinar.webinarcalendarevent"

    createDirectFieldProperties(IWebinarCalendarEvent)

    # Help generating a global unique id for calendar feed exporting, for which
    # we have to make sure each event has a global unique id (uid), such that importing our feed
    # into other third-party calendar wouldn't generate duplicated events if an event is imported twice or more.
    _v_seqNum = 0


class WebinarCalendarEventIO(InterfaceObjectIO):

    _ext_iface_upper_bound = IWebinarCalendarEvent


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ICourseCalendarDynamicEventProvider)
class WebinarCalendarDynamicEventProvider(object):

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def iter_events(self):
        res = []
        calendar = ICourseCalendar(self.course, None)
        for webinar in self._webinars(self.user, self.course):
            seqNum = 0
            for time_session in webinar.times or ():
                if time_session.endTime < time_session.startTime:
                    # CalendarEvent requires endTime can not before startTime.
                    logger.warning("Ignoring the invalid webinar session (subject=%s, webinarKey=%s): endTime (%s) shouldn't before startTime(%s).",
                                    webinar.subject,
                                    webinar.webinarKey,
                                    time_session.endTime,
                                    time_session.startTime)
                    continue
                event = WebinarCalendarEvent(title=webinar.subject or webinar.description or u'Webinar',
                                             description=webinar.description,
                                             start_time=time_session.startTime,
                                             end_time=time_session.endTime,
                                             webinar=webinar)
                event._v_seqNum = seqNum
                event.__parent__ = calendar
                res.append(event)
                seqNum = seqNum + 1
        return res

    def _webinars(self, unused_user, course):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        sites = get_component_hierarchy_names()
        course_ntiids = self._get_course_ntiids(course)
        rs = catalog.search_objects(sites=sites,
                                    intids=intids,
                                    container_ntiids=course_ntiids,
                                    provided=(IWebinarAsset,))
        return set([x.webinar for x in rs or () if x.webinar])

    def _get_course_ntiids(self, instance):
        courses = (instance,)
        parent_course = get_parent_course(instance)
        # We want to check our parent course for refs
        # in the outline, if we have shared outlines.
        if      parent_course != instance \
            and instance.Outline == parent_course.Outline:
            courses = (instance, parent_course)
        return {ICourseCatalogEntry(x).ntiid for x in courses}


@component.adapter(IWebinarCalendarEvent)
@interface.implementer(ICalendarEventUIDProvider)
class WebinarCalendarEventUIDProvider(object):

    def __init__(self, context):
        self.context = context

    def __call__(self):
        return u'{ntiid}_{webinarKey}_{seqNum}'.format(ntiid=to_external_ntiid_oid(self.context.webinar),
                                                       webinarKey=self.context.webinar.webinarKey,
                                                       seqNum=self.context._v_seqNum)
