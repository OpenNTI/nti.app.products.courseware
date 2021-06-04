#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import nameparser

from datetime import datetime

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from requests.structures import CaseInsensitiveDict

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.calendar.views import CalendarEventCreationView
from nti.app.contenttypes.calendar.views import CalendarEventDeletionView
from nti.app.contenttypes.calendar.views import CalendarEventUpdateView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.courseware.interfaces import ACT_RECORD_EVENT_ATTENDANCE
from nti.app.products.courseware.interfaces import ACT_VIEW_EVENT_ATTENDANCE

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contenttypes.calendar.interfaces import ICalendarEvent
from nti.contenttypes.calendar.interfaces import ICalendarEventAttendanceContainer
from nti.contenttypes.calendar.interfaces import IUserCalendarEventAttendance
from nti.contenttypes.calendar.attendance import UserCalendarEventAttendance

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import is_enrolled

from nti.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed

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
