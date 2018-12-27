#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import fudge
import datetime
import unittest

from hamcrest import assert_that
from hamcrest import contains
from hamcrest import has_entries
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import not_none
from hamcrest import same_instance
from hamcrest import starts_with
from hamcrest import contains_inanyorder

from zope.annotation.interfaces import IAnnotations

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.calendar.subscribers import _get_calendar_change_storage
from nti.app.products.courseware.calendar.subscribers import _CHANGE_KEY

from nti.contenttypes.courses.courses import CourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


class TestSubscribers(ApplicationLayerTest):

    @WithMockDSTrans
    @fudge.patch('nti.app.products.courseware.calendar.subscribers._enrolled_principals')
    def test_calendar_change_storage(self, mock_enrolled_principals):
        mock_enrolled_principals.is_callable().returns([])
        course = CourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)

        calendar = ICourseCalendar(course)
        storage = _get_calendar_change_storage(calendar)
        assert_that(storage.__parent__, same_instance(calendar))
        assert_that(storage.__name__, is_(_CHANGE_KEY))
        assert_that(storage, has_length(0))

        annotations = IAnnotations(calendar)
        assert_that(annotations[_CHANGE_KEY], same_instance(storage))

        event = CourseCalendarEvent(title=u'first')
        calendar.store_event(event)
        assert_that(storage, has_length(1))

        change = storage[event.ntiid]
        assert_that(change.object, same_instance(event))
        assert_that(change.__name__, is_(event.ntiid))
        assert_that(change.__parent__, same_instance(storage))
        assert_that(change.sharedWith, is_(None))
        assert_that(change.creator, is_(SYSTEM_USER_NAME))

        event_1 = CourseCalendarEvent(title=u'second')
        event_1.creator = u'abc'
        calendar.store_event(event_1)
        assert_that(storage[event_1.ntiid].creator, is_(u'abc'))

        user = User.create_user(username=u'test001')
        event_2 = CourseCalendarEvent(title=u'third')
        event_2.creator = user
        calendar.store_event(event_2)
        assert_that(storage[event_2.ntiid].creator, same_instance(user))


        mock_enrolled_principals.is_callable().returns([u'test002', u'test003'])
        event_3 = CourseCalendarEvent(title=u'fourth')
        calendar.store_event(event_3)
        assert_that(storage[event_3.ntiid].sharedWith, contains_inanyorder(u'test002', u'test003'))

        assert_that(storage, has_length(4))

        assert_that(calendar.remove_event(event_2), is_(True))
        assert_that(calendar, has_length(3))
        assert_that(storage, has_length(3))
        assert_that([x.object for x in storage.values()], contains_inanyorder(event, event_1, event_3))
