#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime
import fudge

from hamcrest import is_
from hamcrest import ends_with
from hamcrest import not_none
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_length

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.contenttypes.calendar.interfaces import ICalendarEventUIDProvider

from nti.app.products.webinar.client_models import Webinar
from nti.app.products.webinar.client_models import WebinarSession

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware.webinars.calendar import WebinarCalendarEvent
from nti.app.products.courseware.webinars.calendar import WebinarCalendarDynamicEventProvider

from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.dataserver.tests import mock_dataserver

from nti.externalization import internalization

from nti.externalization.externalization import toExternalObject

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.oids import to_external_ntiid_oid


def _make_webinar(subject=u'', description=u'abc', times=((1539993600,1539993620),)):
    ts = []
    for start, end in times:
        sess = WebinarSession(startTime=datetime.datetime.utcfromtimestamp(start),
                              endTime=datetime.datetime.utcfromtimestamp(end))
        ts.append(sess)
    return Webinar(subject=subject,
                   description=description,
                   organizerKey=u'',
                   webinarKey=u'',
                   timeZone=u'US/Central',
                   webinarID=u'123456',
                   inSession=False,
                   times=ts)


class TestCalendar(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def testWebinarCalendarEvent(self):
        with mock_dataserver.mock_db_trans(self.ds):
            webinar = _make_webinar()
            obj =  WebinarCalendarEvent(title=u'reading',
                                        description=u'this is',
                                        location=u'oklahoma',
                                        webinar=webinar)
            external = toExternalObject(obj)
            assert_that(external, has_entries({'title': 'reading',
                                               'description': 'this is',
                                               'location': 'oklahoma',
                                               'start_time': not_none(),
                                               'Class': 'WebinarCalendarEvent',
                                               'MimeType': 'application/vnd.nextthought.webinar.webinarcalendarevent'}))

            # Should not be created externally.
            factory = internalization.find_factory_for(external)
            assert_that(factory, is_(None))

    @WithSharedApplicationMockDS(testapp=True, users=(u'test001', ))
    @fudge.patch("nti.app.products.courseware.webinars.calendar.WebinarCalendarDynamicEventProvider._webinars")
    def test_iter_events(self, mock_webinars):
        mock_webinars.is_callable().returns([])
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)

            user = User.get_user(u'test001')
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)

            provider = WebinarCalendarDynamicEventProvider(user, course)
            assert_that(provider.iter_events(), has_length(0))

            webinar_one = _make_webinar(subject=u'one')
            mock_webinars.is_callable().returns([webinar_one])
            assert_that(provider.iter_events(), has_length(1))

            webinar_two = _make_webinar(subject=u'two', times=((1539993600,1539993620),
                                                               (1539993601,1539993621)))
            mock_webinars.is_callable().returns([webinar_two])
            assert_that(provider.iter_events(), has_length(2))

            mock_webinars.is_callable().returns([webinar_one, webinar_two])
            assert_that(provider.iter_events(), has_length(3))


    def _create_group(self, overview_ntiid, admin_env):
        href = '/dataserver2/Objects/%s/contents/index/0' % overview_ntiid
        params = {
            "MimeType":"application/vnd.nextthought.nticourseoverviewgroup",
            "title":"1",
            "accentColor":"F9824E"
        }
        res = self.testapp.post_json(href, params=params, status=201, extra_environ=admin_env).json_body
        return res['NTIID']

    @WithSharedApplicationMockDS(testapp=True, users=(u'test001', u'admin001@nextthought.com'))
    def test_webinars(self):
        admin_env = self._make_extra_environ(username='admin001@nextthought.com')
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            course_oid = toExternalObject(course)['OID']

            unit_ntiid = u'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2013_CLC3403_LawAndJustice.0'
            lesson_ntiid = u'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2013_CLC3403_LawAndJustice.0.0'
            lesson = course.Outline[unit_ntiid][lesson_ntiid]
            overview = INTILessonOverview(lesson)
            overview_ntiid = to_external_ntiid_oid(overview)

        group_ntiid = self._create_group(overview_ntiid, admin_env)
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            group = find_object_with_ntiid(group_ntiid)
            group_oid = to_external_ntiid_oid(group)

        # create webinar asset.
        href = '/dataserver2/Objects/%s/contents/index/0' % group_oid
        params = {
            'MimeType': 'application/vnd.nextthought.webinarasset',
            'webinar': {
                'MimeType': 'application/vnd.nextthought.webinar',
                'times': [
                    {
                        'MimeType': 'application/vnd.nextthought.webinarsession',
                        'startTime': '2018-09-12T00:00:00Z',
                        'endTime': '2018-09-11T00:00:00Z'
                    },
                    {
                        'MimeType': 'application/vnd.nextthought.webinarsession',
                        'startTime': '2018-09-10T00:00:00Z',
                        'endTime': '2018-09-10T01:00:00Z'
                    },
                    {
                        'MimeType': 'application/vnd.nextthought.webinarsession',
                        'startTime': '2018-09-11T00:00:00Z',
                        'endTime': '2018-09-11T02:00:00Z'
                    }
                ],
                'subject': u'Sample',
                'description': u'For testing',
                'organizerKey': u'org100',
                'webinarKey': u'web100',
                'timeZone': u'US/Central',
                'inSession': False,
                'webinarID': u'123456'
            }
        }
        res = self.testapp.post_json(href, params=params, status=201, extra_environ=admin_env).json_body
        asset_ntiid= res['NTIID']

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = User.get_user(u'test001')
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)

            provider = WebinarCalendarDynamicEventProvider(user, course)
            events = provider.iter_events()
            assert_that(events, has_length(2))
            assert_that(events[0].title, is_('Sample'))
            assert_that(events[0].description, is_('For testing'))
            assert_that(events[0].start_time.strftime('%Y-%m-%d %H:%M:%S'), is_('2018-09-10 00:00:00'))
            assert_that(events[0].end_time.strftime('%Y-%m-%d %H:%M:%S'), is_('2018-09-10 01:00:00'))

            assert_that(events[1].title, is_('Sample'))
            assert_that(events[1].description, is_('For testing'))
            assert_that(events[1].start_time.strftime('%Y-%m-%d %H:%M:%S'), is_('2018-09-11 00:00:00'))
            assert_that(events[1].end_time.strftime('%Y-%m-%d %H:%M:%S'), is_('2018-09-11 02:00:00'))
            assert_that(ICalendarEventUIDProvider(events[1])(), ends_with('_web100_1'))

        href = '/dataserver2/Objects/%s/contents/ntiid/%s?index=0' % (group_oid, asset_ntiid)
        self.testapp.delete(href, status=200, extra_environ=admin_env)
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            provider = WebinarCalendarDynamicEventProvider(user, course)
            events = provider.iter_events()
            assert_that(events, has_length(0))

            # Currently the original webinar is still in the course container.
            assert_that(ICourseWebinarContainer(course), has_length(1))
