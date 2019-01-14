#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from datetime import datetime

import fudge

from hamcrest import is_
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder

from zope import component
from zope import interface

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.contenttypes.calendar.interfaces import ICalendar
from nti.contenttypes.calendar.utils import get_indexed_calendar_events

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.tests import mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


class TestIndex(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice'

    def _new_event(self, title, creator=None):
        event = CourseCalendarEvent(title=u'work')
        event.creator = User.get_user(u'admin001@nextthought.com') if creator is None else creator
        return event

    @WithSharedApplicationMockDS(testapp=True, users=(u'admin001@nextthought.com',))
    def test_get_indexed_calendar_events(self):
        admin_env = self._make_extra_environ('admin001@nextthought.com')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            calendar = ICalendar(course)

            event_one = calendar.store_event(self._new_event(title=u'work'))
            event_two = calendar.store_event(self._new_event(title=u'hobby'))
            event_three = calendar.store_event(self._new_event(title=u'math'))

            res = get_indexed_calendar_events(contexts=(entry,))
            assert_that(res, contains_inanyorder(event_one, event_two, event_three))

            res = get_indexed_calendar_events(contexts=(entry.ntiid))
            assert_that(res, contains_inanyorder(event_one, event_two, event_three))

            res = get_indexed_calendar_events(sites='platform.ou.edu')
            assert_that(res, contains_inanyorder(event_one, event_two, event_three))

            child = course.SubInstances['01']
            child_entry = ICourseCatalogEntry(child)
            event_four = ICalendar(child).store_event(self._new_event(title=u'child_title'))

            res = get_indexed_calendar_events(sites='platform.ou.edu')
            assert_that(res, contains_inanyorder(event_one, event_two, event_three, event_four))

            res = get_indexed_calendar_events(contexts=(entry,))
            assert_that(res, contains_inanyorder(event_one, event_two, event_three))

            res = get_indexed_calendar_events(contexts=(child_entry,))
            assert_that(res, contains_inanyorder(event_four))

            res = get_indexed_calendar_events(contexts=(entry, child_entry))
            assert_that(res, contains_inanyorder(event_one, event_two, event_three, event_four))
