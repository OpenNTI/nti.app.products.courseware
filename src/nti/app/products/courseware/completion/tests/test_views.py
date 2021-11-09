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
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import fudge

from persistent import Persistent

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.schema.interfaces import ConstraintNotSatisfied

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.contenttypes.completion import AWARDED_COMPLETED_ITEMS_PATH_NAME

from nti.app.contenttypes.completion.tests.models import PersistentCompletableItem

from nti.app.products.courseware_admin import VIEW_COURSE_ROLES

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.completion.views import _html_as_rml_fragments

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
from nti.app.products.courseware.tests import SharedConfiguringTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import IAwardedCompletedItemContainer
from nti.contenttypes.completion.interfaces import IPrincipalAwardedCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IContained

from nti.dataserver.authorization import ROLE_SITE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface


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
        

class TestAdminAwardedCompletedViews(ApplicationLayerTest):
    
    layer = PersistentInstructedCourseApplicationTestLayer
    
    default_origin = 'http://platform.ou.edu'
    
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    
    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.contenttypes.completion.policies.CompletableItemAggregateCompletionPolicy.is_complete')
    def test_awarded_completed_items(self, mock_is_complete):
        
        awarded_user_username = u'rocket.raccoon'
        
        test_site_admin_username = u'I.Am.Groot'
        
        course_admin_username = u'peter.quill'
        
        course_editor_username = u'drax.destroyer'
        
        # Setup
        with mock_dataserver.mock_db_trans(self.ds):
            awarded_user = self._create_user(awarded_user_username)
            course_admin = self._create_user(course_admin_username)
            course_editor = self._create_user(course_editor_username)
            set_user_creation_site(awarded_user, 'platform.ou.edu')
            set_user_creation_site(course_admin, 'platform.ou.edu')
            set_user_creation_site(course_editor, 'platform.ou.edu')
                   
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            user = User.get_user(awarded_user_username)
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
            
            completion_context = find_interface(entry, ICompletionContext)
            item1 = PersistentCompletableItem('ntiid1')
            item2 = PersistentCompletableItem('ntiid2')
            non_contained_item = PersistentCompletableItem('non_contained_item')
            item1.containerId = 'container_id'
            item2.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            user = User.get_user(course_admin_username)
            for item in (item1, item2):
                user.addContainedObject(item)
            item_ntiid1 = to_external_ntiid_oid(item1)
            item1.ntiid = item_ntiid1
            item_ntiid2 = to_external_ntiid_oid(item2)
            item2.ntiid = item_ntiid2
            non_contained_item_ntiid = to_external_ntiid_oid(non_contained_item)
            non_contained_item.ntiid = non_contained_item_ntiid
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            principal_role_manager.assignRoleToPrincipal(ROLE_CONTENT_EDITOR.id,
                                                         course_admin_username)
            
            entry = find_object_with_ntiid(self.course_ntiid)
            course_oid = to_external_ntiid_oid(ICourseInstance(entry))
        
        course_admin_environ = self._make_extra_environ(user=course_admin_username)
        course_editor_environ = self._make_extra_environ(course_editor_username)
        user_environ = self._make_extra_environ(awarded_user_username)
        nt_admin_environ = self._make_extra_environ()
        
        # Admin links
        course = self.testapp.get('/dataserver2/Objects/%s' % course_oid)
        course_ext = course.json_body
        course_roles_href = self.require_link_href_with_rel(course_ext, VIEW_COURSE_ROLES)
        
        data = dict()
        data['roles'] = roles = dict()
        roles['instructors'] = list([course_admin_username])
        roles['editors'] = list([course_editor_username])

        #Set up instructor
        self.testapp.put_json(course_roles_href, data)
        
        def get_enr():
            res = self.testapp.get('/dataserver2/users/%s/Courses/EnrolledCourses' % awarded_user_username,
                                   extra_environ=user_environ)
            res = res.json_body['Items'][0]
            return res
        
        enr_res = get_enr()
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            awarded_user = User.get_user(awarded_user_username)
            user_awarded_container = component.getMultiAdapter((awarded_user, completion_context),
                                                       IPrincipalAwardedCompletedItemContainer)
            course_awarded_container = IAwardedCompletedItemContainer(completion_context)
            assert_that(user_awarded_container.get_completed_item_count(), is_(0))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(0))
            
        award_completed_url = self.require_link_href_with_rel(enr_res, AWARDED_COMPLETED_ITEMS_PATH_NAME)
        data = {'MimeType': 'application/vnd.nextthought.completion.awardedcompleteditem', 'completable_ntiid': item_ntiid1}
        
        # Check permissions
        self.testapp.post_json(award_completed_url, data, extra_environ=user_environ, status=403)
        self.testapp.post_json(award_completed_url, data, extra_environ=course_editor_environ, status=403)
        
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

            assert_that(res.json_body, not has_key('Item'))
            assert_that(res.json_body, not has_key('Principal'))
            assert_that(res.json_body, has_key('awarder'))
            
            assert_that(res.json_body['reason'], is_(None))
            
            assert_that(user_awarded_container.get_completed_item_count(), is_(1))
            assert_that(user_awarded_container[item_ntiid1].awarder.username, is_(course_admin_username))
            assert_that(user_awarded_container[item_ntiid1].Principal.username, is_(awarded_user_username))
            assert_that(user_awarded_container[item_ntiid1].Item, is_(item1))
            
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(0))
         
        # Should work even without MimeType explicitly passed in   
        data = {'completable_ntiid': item_ntiid2, 'reason': 'Good soup'}
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(res.json_body['reason'], is_('Good soup'))
            assert_that(user_awarded_container.get_completed_item_count(), is_(2))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(1))
            
        # POST completable that already exists; test 409 and being able to overwrite
        data['reason'] = 'Number one'    
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=409)
        
        overwrite_awarded_link = self.require_link_href_with_rel(res.json_body, 'overwrite')
        res = self.testapp.post_json(overwrite_awarded_link, data, extra_environ=course_admin_environ)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(res.json_body['reason'], is_('Number one'))
            assert_that(user_awarded_container.get_completed_item_count(), is_(2))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(1))
            
        # POST with ntiid that doesn't match an item and with item ntiid that doesn't map to completable in course; both should 422
        data = {'completable_ntiid': non_contained_item_ntiid}
        self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=422)
        
        data = {'completable_ntiid': 'not_a_valid_ntiid'}
        self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=422)

        #Test deletion of AwardedCompletedItem
        delete_awarded_link = self.require_link_href_with_rel(res.json_body, 'edit')
        self.testapp.delete(delete_awarded_link)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(user_awarded_container.get_completed_item_count(), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(0))
