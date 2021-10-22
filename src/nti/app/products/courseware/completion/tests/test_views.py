#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime

import unittest

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_string
does_not = is_not

import fudge

from persistent import Persistent

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.event import notify

from zope.schema.interfaces import ConstraintNotSatisfied

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
from nti.app.products.courseware.tests import SharedConfiguringTestLayer

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.completion.views import _html_as_rml_fragments


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
    entry_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/CourseCatalogEntry'


    def _completed_item(self, success):
        return CompletedItem(Item=MockCompletableItem(u'tag:nextthought.com,2011-10:Test001'),
                             Principal=MockPrincipal(),
                             CompletedDate=datetime.datetime.utcnow(),
                             Success=success)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.contenttypes.completion.policies.CompletableItemAggregateCompletionPolicy.is_complete')
    def test_certificate(self, mock_is_complete):
        mock_is_complete.is_callable().returns(None)
        
        # Setup
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('user001_cert')
            self._create_user('siteadmin_cert')
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            user = User.get_user('user001_cert')
            set_user_creation_site(user)
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
            
            set_user_creation_site(User.get_user('siteadmin_cert'))
            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, 'siteadmin_cert')
        
        user_env = self._make_extra_environ('user001_cert')
        admin_env = self._make_extra_environ('siteadmin_cert')
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
        #self.testapp.get(cert_href, extra_environ=user_env)
        
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
            assert_that(calling(setattr).with_args(policy, 'certificate_renderer_name', 'cert_render_that_dne'),
                    raises(ConstraintNotSatisfied))
            policy.__dict__['certificate_renderer_name'] = 'cert_render_that_dne'
            
            
        entry_res = self.testapp.get(self.entry_href).json_body
        vocab_href = self.require_link_href_with_rel(entry_res, 'CertificateRenderers')
        vocab_res = self.testapp.get(vocab_href)
        vocab_res = vocab_res.json_body
        terms = vocab_res['terms']
        assert_that(terms, has_length(1))
        assert_that(terms[0], has_entry('value', 'default'))
        
        course_completed_item = self._completed_item(success=True)
        mock_is_complete.is_callable().returns(course_completed_item)
        self.testapp.get(cert_href, extra_environ=user_env)
        # Admins can view too
        self.testapp.get(cert_href, extra_environ=admin_env)
        self.testapp.get(cert_href)

class TestRichDescriptionToRML(unittest.TestCase):

    # We need this layer to ultimately configure nti.contentfragments to deal with the fact
    # that there is a but in nti.contentfragments.html._SanitizerFilter when there is no
    # IHyperlinkFormatter registered
    layer = SharedConfiguringTestLayer

    def test_basic_rich_text(self):
        html_fragment = '<p>This is the step challenge.</p><p>It is very <b>good</b>.</p><p>\\ufeff</p><p><b>How <i>can</i> I <u>help</u> you.</b></p>'

        rml = _html_as_rml_fragments(html_fragment, paraStyle='desc')

        assert_that(rml, is_('<para style="desc">This is the step challenge.</para><para style="desc">It is very <b>good</b>.</para><para style="desc">\\ufeff</para><para style="desc"><b>How <i>can</i> I <u>help</u> you.</b></para>'))

    def test_html_body_converts(self):
        html_fragment = '<html><body><p>This is the step challenge.</p></body></html>'
        rml = _html_as_rml_fragments(html_fragment)
        assert_that(rml, is_('<para>This is the step challenge.</para>'))

    def test_plaintext_passes_through(self):
        html_fragment = 'This is the step challenge.'
        rml = _html_as_rml_fragments(html_fragment)
        assert_that(rml, is_('This is the step challenge.'))

    def test_strip_unsupported_tags(self):
        html_fragment = '<script>alert();</script><p>look <img/>at this</p>'
        rml = _html_as_rml_fragments(html_fragment)
        assert_that(rml, is_('<para>look at this</para>'))
