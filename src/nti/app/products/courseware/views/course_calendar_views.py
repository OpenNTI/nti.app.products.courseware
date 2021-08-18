#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.calendar import EXPORT_ATTENDANCE_VIEW

from nti.app.contenttypes.calendar.authorization import ACT_VIEW_EVENT_ATTENDANCE

from nti.app.contenttypes.calendar.views import ExportAttendanceCSVView
from nti.app.contenttypes.calendar.views import CalendarEventCreationView
from nti.app.contenttypes.calendar.views import CalendarEventDeletionView
from nti.app.contenttypes.calendar.views import CalendarEventUpdateView

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEventAttendanceContainer

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.interfaces import StandardExternalFields

from nti.dataserver import authorization as nauth

from nti.namedfile.file import safe_filename

logger = __import__('logging').getLogger(__name__)

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE
TOTAL = StandardExternalFields.TOTAL


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=ICourseCalendar,
             permission=nauth.ACT_UPDATE)
class CourseCalendarEventCreationView(CalendarEventCreationView):

    @Lazy
    def filer(self):
        course = ICourseInstance(self.context, None)
        return get_course_filer(course, self.remoteUser)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCalendarEvent,
             request_method='PUT',
             permission=nauth.ACT_UPDATE)
class CourseCalendarEventUpdateView(CalendarEventUpdateView):

    @Lazy
    def filer(self):
        course = ICourseInstance(self.context, None)
        return get_course_filer(course, self.remoteUser)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCalendarEvent,
             request_method='DELETE',
             permission=nauth.ACT_UPDATE)
class CourseCalendarEventDeletionView(CalendarEventDeletionView):
    pass


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             renderer='rest',
             context=ICourseCalendarEventAttendanceContainer,
             permission=ACT_VIEW_EVENT_ATTENDANCE,
             name=EXPORT_ATTENDANCE_VIEW)
class CourseCalendarEventExportAttendanceCSVView(ExportAttendanceCSVView):

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def course_catalog_entry(self):
        return ICourseCatalogEntry(self.course)

    def _attendance_record_dict(self, attendance_record):
        result = {
            'Course Name': self.course_catalog_entry.title,
            'Course ID': self.course_catalog_entry.ProviderUniqueID,
        }

        super_result = super(CourseCalendarEventExportAttendanceCSVView, self) \
            ._attendance_record_dict(attendance_record)
        result.update(super_result)

        return result

    def _filename(self):
        filename = "%(puid)s_%(event_name)s_event_attendance.csv" % {
            'puid': self.course_catalog_entry.ProviderUniqueID,
            'event_name': self.event.title,
        }
        return safe_filename(filename)

    def _fieldnames(self):
        fieldnames = ['Course Name', 'Course ID']
        super_fields = super(CourseCalendarEventExportAttendanceCSVView, self)._fieldnames()
        fieldnames.extend(super_fields)
        return fieldnames
