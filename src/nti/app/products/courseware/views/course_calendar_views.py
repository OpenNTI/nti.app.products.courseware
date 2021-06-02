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


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICalendarEventAttendanceContainer,
             permission=ACT_RECORD_EVENT_ATTENDANCE,
             request_method='POST')
class RecordCalendarEventAttendanceView(AbstractAuthenticatedView):
    """
    Post attendance for a given user to an event
    """

    def _is_user_enrolled(self, user, course):
        result = course is not None \
                 and (is_enrolled(course, user))
        return result

    def _get_user(self):
        params = CaseInsensitiveDict(self.request.params)
        username = params.get('user') \
                   or params.get('username') \
                   or params.get('instructor')
        result = User.get_user(username)

        if result is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"User not found."),
                                 'code': 'UserNotFound',
                             },
                             None)

        course = ICourseInstance(self.context, None)
        if not self._is_user_enrolled(result, course):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"User not enrolled."),
                                 'code': 'UserNotEnrolled',
                             },
                             None)

        return result

    def __call__(self):
        user = self._get_user()

        attendance = UserCalendarEventAttendance()
        attendance.creator = self.remoteUser.username
        attendance.registrationTime = datetime.utcnow()

        try:
            self.context.add_attendance(user, attendance)
        except KeyError:
            raise_json_error(self.request,
                             hexc.HTTPConflict,
                             {
                                 'message': _(u"Attendance already marked for user"),
                                 'code': 'DuplicateEntry'
                             },
                             None)

        event = ICalendarEvent(self.context)
        event_ntiid = getattr(event, 'ntiid', None)

        logger.info("'%s' marked attendance at event '%s' for user '%s'",
                    self.getRemoteUser(),
                    event_ntiid,
                    user.username)

        self.request.response.status_int = 201
        return attendance


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUserCalendarEventAttendance,
             request_method='DELETE',
             permission=ACT_RECORD_EVENT_ATTENDANCE)
class CalendarEventAttendanceDeletionView(AbstractAuthenticatedView):

    def __call__(self):
        attendance_container = ICalendarEventAttendanceContainer(self.context)
        attendance_container.remove_attendance(self.context.__name__)
        self.request.response.status_int = 204
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUserCalendarEventAttendance,
             request_method='GET',
             permission=ACT_VIEW_EVENT_ATTENDANCE)
class UserCalendarEventAttendanceView(AbstractAuthenticatedView):

    def __call__(self):
        return self.context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUserCalendarEventAttendance,
             request_method='PUT',
             permission=ACT_RECORD_EVENT_ATTENDANCE)
class UserCalendarEventAttendanceView(UGDPutView):
    pass


class AttendanceSummary(object):

    def __init__(self, attendance, user):
        self.attendance = attendance
        self.user = user

    @Lazy
    def registrationTime(self):
        return self.attendance.registrationTime

    @Lazy
    def creator(self):
        return self.attendance.creator

    @Lazy
    def username(self):
        return getattr(self.user, 'username', '')

    @Lazy
    def alias(self):
        return getattr(IFriendlyNamed(self.user, None), 'alias', '')

    @Lazy
    def realname(self):
        return getattr(IFriendlyNamed(self.user, None), 'realname', '')

    @Lazy
    def last_name(self):
        lastname = u''
        realname = self.realname
        if realname and '@' not in realname and realname != self.username:
            human_name = nameparser.HumanName(realname)
            lastname = human_name.last or u''
        return lastname


@view_config(route_name='objects.generic.traversal',
             permission=ACT_VIEW_EVENT_ATTENDANCE,
             renderer='rest',
             context=ICalendarEventAttendanceContainer,
             request_method='GET')
class CalendarEventAttendanceView(AbstractAuthenticatedView,
                                  BatchingUtilsMixin):
    """
    Return the attendance for the calendar event.

    batchSize
            The size of the batch.  Defaults to 50.

    batchStart
            The starting batch index.  Defaults to 0.

    sortOn
            The case insensitive field to sort on. Options are ``lastname``,
            ``alias``, ``registrationTime``, ``creator``, ``username``.
            The default is by registrationTime.

    sortOrder
            The sort direction. Options are ``ascending`` and
            ``descending``. Sort order is ascending by default.

    """

    _DEFAULT_BATCH_SIZE = 50
    _DEFAULT_BATCH_START = 0

    _default_sort = 'registrationtime'
    _sort_keys = {
        'registrationtime': lambda x: x.registrationTime,
        'username': lambda x: x.username,
        'alias': lambda x: x.alias,
        'realname': lambda x: x.realname,
        'lastname': lambda x: x.last_name,
        'creator': lambda x: x.creator,
    }

    def _get_sorted_result_set(self, summaries, sort_key, sort_desc=False):
        """
        Get the sorted result set.
        """
        summaries = sorted(summaries, key=sort_key, reverse=sort_desc)
        return summaries

    def _get_sort_params(self):
        sort_on = self.request.params.get('sortOn') or ''
        sort_on = sort_on.lower()
        sort_on = sort_on if sort_on in self._sort_keys else self._default_sort
        sort_key = self._sort_keys.get(sort_on)

        # Ascending is default
        sort_order = self.request.params.get('sortOrder')
        sort_descending = bool(
            sort_order and sort_order.lower() == 'descending')

        return sort_key, sort_descending

    def _search_summaries(self, search_param, user_summaries):
        """
        For the given search_param, return the results for those users
        if it matches realname, alias, or displayable username.
        """
        # TODO: Possibly use the entity catalog

        def matches(summary):
            result = (
                    (summary.alias
                     and search_param in summary.alias.lower())
                    or (summary.username
                        and search_param in summary.username.lower())
                    or (summary.last_name
                        and search_param in summary.realname.lower())
            )
            return result

        results = [x for x in user_summaries if matches(x)]
        return results

    def _get_items(self, result_dict):
        """
        Sort and batch records.
        """
        attendance_container = self.context

        # Now build our data for each user
        summaries = []
        for username, attendance in attendance_container.items():
            summary = AttendanceSummary(attendance, User.get_user(username))
            summaries.append(summary)

        search = self.request.params.get('search')
        search_param = search and search.lower()

        if search_param:
            summaries = self._search_summaries(search_param, summaries)

        sort_key, sort_descending = self._get_sort_params()

        result_set = self._get_sorted_result_set(summaries,
                                                 sort_key,
                                                 sort_descending)

        def to_external(summary):
            return summary.attendance

        self._batch_items_iterable(result_dict,
                                   result_set,
                                   selector=to_external)

        return result_dict.get(ITEMS)

    def __call__(self):
        result_dict = LocatedExternalDict()

        result_dict[MIMETYPE] = 'application/vnd.nextthought.calendar.calendareventattendance'
        result_dict[CLASS] = 'CalendarEventAttendance'
        result_dict[ITEMS] = self._get_items(result_dict)

        return result_dict
