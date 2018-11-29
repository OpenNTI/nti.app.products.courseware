#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

import fudge

from hamcrest import assert_that
from hamcrest import is_

from nti.app.products.courseware.calendar.decorators import _CourseCalendarLinkDecorator
from nti.app.products.courseware.calendar.decorators import _CourseCalendarEventCreationLinkDecorator

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.externalization.externalization import toExternalObject


class TestDecorators(ApplicationLayerTest):

    def _decorate(self, decorator, context):
        external = toExternalObject(context, decorate=False)
        decorator = decorator(context, None)
        decorator.decorateExternalMapping(context, external)
        return external

    @WithMockDSTrans
    @fudge.patch('nti.app.products.courseware.calendar.decorators.has_permission')
    def test_course_calendar_link_decorator(self, mock_has_permission):
        mock_has_permission.is_callable().returns(True)
        course = ContentCourseInstance()
        mock_dataserver.current_transaction.add(course)
        external = self._decorate(_CourseCalendarLinkDecorator, course)
        assert_that('CourseCalendar' in [x.rel for x in external['Links']], is_(True))

    @WithMockDSTrans
    @fudge.patch('nti.app.products.courseware.calendar.decorators.has_permission')
    def test_course_calendar_event_creation_link_decorator(self, mock_has_permission):
        mock_has_permission.is_callable().returns(True)
        course = ContentCourseInstance()
        mock_dataserver.current_transaction.add(course)
        external = self._decorate(_CourseCalendarEventCreationLinkDecorator, ICourseCalendar(course))
        assert_that('create_calendar_event' in [x.rel for x in external['Links']], is_(True))
