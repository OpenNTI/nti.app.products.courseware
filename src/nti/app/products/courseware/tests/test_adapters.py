#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import calling
from hamcrest import raises
from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import same_instance

import fudge

from zope import component

from nti.app.products.courseware.adapters import _get_valid_course_context

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.appserver.interfaces import ForbiddenContextException

from nti.contenttypes.courses.courses import CourseInstance

from nti.contenttypes.courses.enrollment import DefaultCourseInstanceEnrollmentRecord

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.coremetadata.interfaces import ILastSeenProvider
from nti.coremetadata.interfaces import IContextLastSeenContainer

from nti.dataserver.tests import mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


class TestAdapters(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

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

    @WithSharedApplicationMockDS(testapp=True, users=(u'test001',))
    @fudge.patch('nti.app.products.courseware.adapters.get_remote_user',
                 'nti.app.products.courseware.adapters._is_catalog_entry_visible')
    def test_get_valid_course_context(self, mock_remote_user, mock_is_catalog_entry_visible):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = User.get_user('test001')
            mock_remote_user.is_callable().returns(user)

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)

            # No enrolled course
            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context(course)
            assert_that(result, has_length(0))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            assert_that(calling(_get_valid_course_context).with_args(course), raises(ForbiddenContextException))

            # Enroll in parent course
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)

            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context(course)
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(course))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            result = _get_valid_course_context(course)
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(course))

            # Drop from parent and enroll in section course
            enrollment_manager.drop(user)
            section_course = course.SubInstances['01']
            enrollment_manager = ICourseEnrollmentManager(section_course)
            enrollment_manager.enroll(user)

            ## pass parent course
            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context(course)
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(section_course))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            result = _get_valid_course_context(course)
            assert_that(result, has_length(2))
            assert_that(result[0], same_instance(section_course))
            assert_that(ICourseCatalogEntry.providedBy(result[1]), is_(True))

            ## pass section course
            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context(section_course)
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(section_course))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            result = _get_valid_course_context(section_course)
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(section_course))

            ## pass both, only section course returned.
            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context((course, section_course))
            assert_that(result, has_length(1))
            assert_that(result[0], same_instance(section_course))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            result = _get_valid_course_context((course, section_course))
            assert_that(result, has_length(2))
            assert_that(result[0], same_instance(section_course))
            assert_that(ICourseCatalogEntry.providedBy(result[1]), is_(True))

            result = _get_valid_course_context((section_course, course))
            assert_that(result, has_length(2))
            assert_that(result[0], same_instance(section_course))
            assert_that(ICourseCatalogEntry.providedBy(result[1]), is_(True))

            # drop from section course
            enrollment_manager.drop(user)
            mock_is_catalog_entry_visible.is_callable().returns(False)
            result = _get_valid_course_context(section_course)
            assert_that(result, has_length(0))

            mock_is_catalog_entry_visible.is_callable().returns(True)
            assert_that(calling(_get_valid_course_context).with_args(section_course), raises(ForbiddenContextException))
