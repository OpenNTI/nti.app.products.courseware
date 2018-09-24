#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import assert_that

import fudge

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.enrollment import DefaultCourseInstanceEnrollmentRecord

from nti.coremetadata.interfaces import ILastSeenProvider
from nti.coremetadata.interfaces import IContextLastSeenContainer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestAdapters(ApplicationLayerTest):

    @WithMockDSTrans
    @fudge.patch("nti.contenttypes.courses.courses.to_external_ntiid_oid")
    def test_course_last_seen_time_to_user(self, mock_to_external_ntiid_oid):
        mock_to_external_ntiid_oid.is_callable().returns("ntiid_abc")
        user = self._create_user(username=u'test001')
        course = CourseInstance()

        provider = component.queryMultiAdapter((user, course), ILastSeenProvider)
        assert_that(provider.lastSeenTime, is_(None))

        # pylint: disable=too-many-function-args
        container = IContextLastSeenContainer(user)
        container.append(course.ntiid, 1533445200)

        provider = component.getMultiAdapter((user, course), ILastSeenProvider)
        assert_that(provider.lastSeenTime.strftime('%Y-%m-%d %H:%M:%S'),
                    is_("2018-08-05 05:00:00"))

    @WithMockDSTrans
    @fudge.patch("nti.contenttypes.courses.courses.to_external_ntiid_oid",
                 "nti.contenttypes.courses.enrollment.DefaultCourseEnrollments.get_enrollment_for_principal")
    def test_course_enrollment_record_last_seen_time(self, mock_to_external_ntiid_oid, mock_enrollment):
        mock_to_external_ntiid_oid.is_callable().returns("ntiid_abc")
        user = self._create_user(username=u'test001')
        record = DefaultCourseInstanceEnrollmentRecord(Principal=user)
        record.createdTime = None
        class _MockStorage(object):
            pass
        # pylint: disable=attribute-defined-outside-init
        record.__parent__ = _MockStorage()
        record.__parent__.__parent__ = CourseInstance()

        mock_enrollment.is_callable().returns(record)

        provider = ILastSeenProvider(record, None)
        assert_that(provider.lastSeenTime, is_(None))

        # pylint: disable=too-many-function-args
        container = IContextLastSeenContainer(user, None)
        container.append(u'ntiid_abc', 1533445200)

        provider = ILastSeenProvider(record, None)
        # pylint: disable=no-member  
        assert_that(provider.lastSeenTime.strftime('%Y-%m-%d %H:%M:%S'), is_("2018-08-05 05:00:00"))

        # Use enrollment date.
        container.pop(u'ntiid_abc')
        record.createdTime = 1533790800

        provider = ILastSeenProvider(record, None)
        # pylint: disable=no-member
        assert_that(provider.lastSeenTime.strftime('%Y-%m-%d %H:%M:%S'), is_("2018-08-09 05:00:00"))