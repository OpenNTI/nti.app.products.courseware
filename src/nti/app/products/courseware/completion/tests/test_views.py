#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_string
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
from nti.ntiids.ntiids import find_object_with_ntiid
from nti.app.products.courseware import VIEW_CERTIFICATE
does_not = is_not

import fudge

from persistent import Persistent

from quopri import decodestring

from zope import component
from zope import interface

from zope.event import notify

from zope.security.interfaces import IPrincipal

from nti.app.testing.testing import ITestMailDelivery

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import CourseCompletedEvent
from nti.contenttypes.courses.interfaces import ICourseCompletedEvent
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IUserProfile


@interface.implementer(IPrincipal)
class MockPrincipal(Persistent):
    username = id = title = u'user001_cert'

    __name__ = None
    __parent__ = None
    description = u''

    def __call__(self):
        return self

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __lt__(self, other):
        if other is not self:
            return True
        return False


class TestViews(ApplicationLayerTest):
    
    layer = PersistentInstructedCourseApplicationTestLayer
    
    default_origin = 'http://janux.ou.edu'
    
    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def _completed_item(self, success):
        return CompletedItem(Item=MockCompletableItem(u'tag:nextthought.com,2011-10:Test001'),
                             Principal=MockPrincipal(),
                             CompletedDate=datetime.datetime.utcnow(),
                             Success=success)

    # _user_completed_item = None
    # class _MockCompletionPolicy(CompletableItemAggregateCompletionPolicy):
    #     def is_complete(self, unused_progress):
    #         return self._user_completed_item

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.contenttypes.completion.policies.CompletableItemAggregateCompletionPolicy.is_complete')
    def test_certificate(self, mock_is_complete):
        mock_is_complete.is_callable().returns(None)
        
        # Setup
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('user001_cert')
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            user = User.get_user('user001_cert')
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
        
        user_env = self._make_extra_environ('user001_cert')
        def get_enr():
            res = self.testapp.get('/dataserver2/users/user001_cert/Courses/EnrolledCourses',
                                   extra_environ=user_env)
            res = res.json_body['Items'][0]
            return res
        
        # No policy
        enr_res = get_enr()
        self.forbid_link_with_rel(enr_res, VIEW_CERTIFICATE)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            policy = CompletableItemAggregateCompletionPolicy()
            policy.percentage = 1.0
            policy.offers_completion_certificate = False
            policy_container = ICompletionContextCompletionPolicyContainer(course)
            policy_container.context_policy = policy
            
        # No cert
        enr_res = get_enr()
        self.forbid_link_with_rel(enr_res, VIEW_CERTIFICATE)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            policy = ICompletionContextCompletionPolicy(course)
            policy.offers_completion_certificate = True
        
        # Incomplete
        enr_res = get_enr()
        self.forbid_link_with_rel(enr_res, VIEW_CERTIFICATE)
        
        # Now with completed item
        course_completed_item = self._completed_item(success=True)
        mock_is_complete.is_callable().returns(course_completed_item)
        enr_res = get_enr()
        cert_href = self.require_link_href_with_rel(enr_res, VIEW_CERTIFICATE)
        self.testapp.get(cert_href, extra_environ=user_env)
        
        # Unsuccessful
        course_completed_item = self._completed_item(success=False)
        mock_is_complete.is_callable().returns(course_completed_item)
        self.testapp.get(cert_href, extra_environ=user_env, status=404)
        
        # Course points to template that was removed at some point
        # We fall back to default
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            policy = ICompletionContextCompletionPolicy(course)
            policy.certificate_renderer_name = u'cert_render_that_dne'
        course_completed_item = self._completed_item(success=True)
        mock_is_complete.is_callable().returns(course_completed_item)
        self.testapp.get(cert_href, extra_environ=user_env)
