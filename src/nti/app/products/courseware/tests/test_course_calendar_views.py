#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import has_properties
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than

from zope import component

from zope.annotation.interfaces import IAnnotations

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver


class TestCourseCalendarViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_calendar_views(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            assert_that('CourseCalendar' in IAnnotations(course), is_(False))

        # empty read
        calendar_url = self.course_url + "/CourseCalendar"
        result = self.testapp.get(calendar_url, status=200).json_body
        assert_that(result, has_entries({'Items': has_length(0)}))

        result = self.testapp.get(calendar_url, params={'raw': True}, status=200).json_body
        assert_that(result, has_entries({'title': '',
                                         'description': None,
                                         'MimeType': 'application/vnd.nextthought.courseware.coursecalendar'}))

        # update calendar
        result = self.testapp.put_json(calendar_url, params={'title': 'calen', 'description': 'this'}, status=200).json_body
        assert_that(result, has_entries({'title': 'calen',
                                         'description': 'this',
                                         'MimeType': 'application/vnd.nextthought.courseware.coursecalendar'}))

        # add calendar event
        params = {
            "MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
            "title": "go to school",
            "description": "let us go",
            "icon": "/home/go",
            "location": "oklahoma",
            "start_time": "2018-09-20T09:00Z",
            "end_time": "2018-09-20T12:00Z"
        }
        res = self.testapp.post_json(calendar_url, params=params, status=201).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "title": "go to school",
                                      "description": "let us go",
                                      "icon": "/home/go",
                                      "location": "oklahoma",
                                      "start_time": "2018-09-20T09:00:00Z",
                                      "end_time": "2018-09-20T12:00:00Z",
                                      "Last Modified": not_none(),
                                      "NTIID": not_none()}))
        event_ntiid = res['NTIID']
        event_oid = res['OID']
        event_url = '/dataserver2/Objects/%s' % event_oid

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that('CourseCalendar' in IAnnotations(course), is_(True))

            calendar = ICourseCalendar(course)
            assert_that(calendar, has_length(1))
            event = calendar.retrieve_event(event_ntiid)
            assert_that(event, has_properties({'title': 'go to school',
                                               'description': 'let us go',
                                               'icon': '/home/go',
                                               'location': 'oklahoma',
                                               'start_time': not_none(),
                                               'end_time': not_none()}))

        # read calendar event
        res = self.testapp.get(event_url, status=200).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "NTIID": event_ntiid}))


        # update calendar event
        params = {'title': 'okay'}
        res = self.testapp.put_json(event_url, params=params, status=200).json_body
        assert_that(res, has_entries({"MimeType": "application/vnd.nextthought.courseware.coursecalendarevent",
                                      "NTIID": event_ntiid,
                                      "title": "okay"}))

        # fetch non-empty calendar
        result = self.testapp.get(calendar_url, status=200).json_body
        assert_that(result, has_entries({'Items': has_length(1)}))

        # delete calendar event
        self.testapp.delete(event_url, status=204)

        # verify deleted event
        result = self.testapp.get(calendar_url, status=200).json_body
        assert_that(result, has_entries({'Items': has_length(0)}))
        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(calendar, has_length(0))
