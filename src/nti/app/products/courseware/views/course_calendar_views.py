#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config


from nti.app.contenttypes.calendar.views import CalendarEventCreationView
from nti.app.contenttypes.calendar.views import CalendarEventDeletionView

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.dataserver import authorization as nauth


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=ICourseCalendar,
             permission=nauth.ACT_UPDATE)
class CourseCalendarEventCreationView(CalendarEventCreationView):
    pass


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCalendarEvent,
             request_method='DELETE',
             permission=nauth.ACT_UPDATE)
class CourseCalendarEventDeletionView(CalendarEventDeletionView):
    pass
