#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
from hamcrest import contains_inanyorder
does_not = is_not

from quopri import decodestring

from zope import component

from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS

from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.app.products.courseware.invitations.utils import create_course_invitation

from nti.contenttypes.courses.interfaces import ES_CREDIT

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollments

from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.externalization import StandardExternalFields

from nti.invitations.interfaces import IInvitationsContainer

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.testing import ITestMailDelivery

from nti.dataserver.tests import mock_dataserver

ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
NTIID = StandardExternalFields.NTIID
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


class TestInvitations(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @classmethod
    def catalog_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_invitations(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            course_ntiid = to_external_ntiid_oid(course)

        environ = self._make_extra_environ(username='harp4162')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'

        url = '/dataserver2/Objects/%s' % course_ntiid
        res = self.testapp.get(url, extra_environ=environ, status=200)
        access_token_href = self.require_link_href_with_rel(res.json_body,
                                                            VIEW_COURSE_ACCESS_TOKENS)

        res = self.testapp.get(access_token_href,
                               extra_environ=environ,
                               status=200)
        assert_that(res.json_body,
                    has_entry(ITEMS, has_length(1)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_persistent_invitations(self):
        """
        Test persistent course invitations.
        """
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(u'ichigo')
            IUserProfile(user).email = u'ichigo@bleach.org'

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            invitations = ICourseInvitations(course)
            assert_that(invitations, has_length(0))
            assert_that(invitations.get_course_invitations(), has_length(0))
            course_ntiid = to_external_ntiid_oid(course)

            # Now create one
            invitation1 = create_course_invitation(course)
            code1 = invitation1.code
            assert_that(code1, not_none())

            code2 = u'test_invitation_code'
            invitation2 = create_course_invitation(course,
                                                   scope=ES_CREDIT,
                                                   is_generic=True,
                                                   code=code2)
            assert_that(invitation2.code, is_(code2))
            assert_that(invitation2.IsGeneric, is_(True))
            assert_that(invitation2.scope, is_(ES_CREDIT))
            invitations = ICourseInvitations(course)
            assert_that(invitations, has_length(2))
            assert_that(invitations.get_course_invitations(),
                        has_length(2))
            invitations = invitations.get_course_invitations()
            assert_that([x.code for x in invitations],
                        contains_inanyorder(code1, code2))

        environ = self._make_extra_environ(username='harp4162')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'

        url = '/dataserver2/Objects/%s' % course_ntiid
        res = self.testapp.get(url, extra_environ=environ, status=200)
        access_token_href = self.require_link_href_with_rel(res.json_body,
                                                            VIEW_COURSE_ACCESS_TOKENS)

        res = self.testapp.get(access_token_href,
                               extra_environ=environ,
                               status=200)
        res = res.json_body
        invitations = res[ITEMS]
        assert_that(invitations, has_length(3))
        for invitation in invitations:
            assert_that(invitation[CLASS], is_('CourseInvitation'))
            if NTIID in invitation:
                # Persistent
                assert_that(invitation[CREATED_TIME], not_none())
                assert_that(invitation[LAST_MODIFIED], not_none())
        assert_that(invitations, has_item(has_entry('Code', code1)))
        assert_that(invitations, has_item(has_entry('Code', code2)))

        # Validate accepting
        accept_url = '/dataserver2/users/ichigo/accept-course-invitations?code=%s' % code2
        user_environ = self._make_extra_environ(username='ichigo')
        user_environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        self.testapp.get(accept_url, extra_environ=user_environ)

        # Now remove both and re-fetch
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            invitations = ICourseInvitations(course)
            invitation_container = component.getUtility(IInvitationsContainer)
            invitation1 = invitation_container.get_invitation_by_code(code1)
            assert_that(invitation1, not_none())
            assert_that(invitations.remove(invitation1), is_(True))
            assert_that(invitations, has_length(1))
            assert_that(invitations.get_course_invitations()[0].code,
                        is_(code2))

            # Remove from container will clean up course ref
            invitation2 = invitation_container.get_invitation_by_code(code2)
            assert_that(invitation2, not_none())
            assert_that(invitation_container.remove(invitation2), is_(True))
            assert_that(invitations, has_length(0))
            assert_that(invitations._invitation_wrefs, has_length(0))

        res = self.testapp.get(access_token_href,
                               extra_environ=environ,
                               status=200)
        res = res.json_body
        invitations = res[ITEMS]
        assert_that(invitations, has_length(1))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_accept_invitation(self):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(u'ichigo')
            IUserProfile(user).email = u'ichigo@bleach.org'

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            course_ntiid = to_external_ntiid_oid(course)

        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]

        environ = self._make_extra_environ(username='harp4162')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        data = {'username': 'ichigo', 'code': "CI-CLC-3403"}
        url = '/dataserver2/Objects/%s/SendCourseInvitations' % course_ntiid
        res = self.testapp.post_json(url, data,
                                     extra_environ=environ, status=200)
        assert_that(res.json_body, has_entry(ITEMS, has_length(1)))
        code = res.json_body[ITEMS][0]['code']

        mailer = component.getUtility(ITestMailDelivery)
        msg = mailer.queue[0]
        html = decodestring(msg.html)
        assert_that(html,
                    contains_string('/accept-course-invitations?code=%s' % code))

        accept_url = '/dataserver2/users/ichigo/accept-course-invitations?code=%s' % code
        environ = self._make_extra_environ(username='ichigo')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        # Redirected to app form
        res = self.testapp.get(accept_url, extra_environ=environ, status=302)
        assert_that(res.location,
                    is_('http://localhost/app/catalog/redeem/%s' % code))

        # Now submitted
        environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        self.testapp.get(accept_url, extra_environ=environ, status=200)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(get_enrollments('ichigo'), has_length(1))

        # Invitation already accepted.
        self.testapp.get(accept_url, extra_environ=environ, status=422)

        environ = self._make_extra_environ(username='harp4162')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        data = {'name': 'ichigo', 'email': 'ichigo@bleach.org',
                'code': 'CI-CLC-3403'}
        url = '/dataserver2/Objects/%s/SendCourseInvitations' % course_ntiid
        self.testapp.post_json(url, data, extra_environ=environ, status=200)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_generic_invitation(self):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(u'ichigo')
            IUserProfile(user).email = u'ichigo@bleach.org'

        code = "CI-CLC-3403"
        accept_url = '/dataserver2/users/ichigo/accept-course-invitations?code=%s' % code
        environ = self._make_extra_environ(username='ichigo')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        # Redirected to app form
        res = self.testapp.get(accept_url, extra_environ=environ, status=302)
        assert_that(res.location,
                    is_('http://localhost/app/catalog/redeem/%s' % code))

        # Now submitted
        environ['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        self.testapp.get(accept_url, extra_environ=environ, status=200)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(get_enrollments('ichigo'), has_length(1))

        # Already enrolled
        self.testapp.get(accept_url, extra_environ=environ, status=403)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_check_course_inv_csv(self):
        base_source = [
            'ichigo@bleach.org, "ichigo kurosaki"',
            'aizen@bleach.org, "azien sosuke"',
            'invalid, "invalid_email"',
        ]
        source = str('\n'.join(base_source))
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            course_ntiid = to_external_ntiid_oid(course)

        environ = self._make_extra_environ(username='harp4162')
        environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        cvs_url = '/dataserver2/Objects/%s/CheckCourseInvitationsCSV' % course_ntiid
        res = self.testapp.post(cvs_url,
                                upload_files=[('input', 'source.csv', source)],
                                status=200)

        assert_that(res.json_body, has_entry(ITEMS, has_length(2)))
        invalid_emails = res.json_body.get('InvalidEmails')
        assert_that(invalid_emails.get('message'), not_none())
        assert_that(invalid_emails.get('Items'), contains('invalid'))

        data = dict(res.json_body)
        data.pop('Warnings', None)

        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]

        url = '/dataserver2/Objects/%s/SendCourseInvitations' % course_ntiid
        res = self.testapp.post_json(url, data,
                                     extra_environ=environ,
                                     status=200)
        assert_that(res.json_body, has_entry(ITEMS, has_length(2)))

        # Now CR only
        source = str('\r'.join(base_source))
        res = self.testapp.post(cvs_url,
                                upload_files=[('input', 'source.csv', source)],
                                status=200)
