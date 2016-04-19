#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
does_not = is_not

from quopri import decodestring

from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.invitation import JoinCourseInvitation

from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.externalization import StandardExternalFields

from nti.externalization.oids import to_external_ntiid_oid

from nti.invitations.interfaces import IInvitations

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.testing import ITestMailDelivery

from nti.dataserver.tests import mock_dataserver

ITEMS = StandardExternalFields.ITEMS

class TestInvitations(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	@classmethod
	def catalog_entry(cls):
		return find_object_with_ntiid(cls.entry_ntiid)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_get_invitations(self):

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			invitiation = JoinCourseInvitation("CLC3403", self.entry_ntiid)
			component.getGlobalSiteManager().registerUtility(invitiation,
															 IJoinCourseInvitation,
															 "CLC3403")
			entry = self.catalog_entry()
			course = ICourseInstance(entry)
			course_ntiid = to_external_ntiid_oid(course)

		environ = self._make_extra_environ(username='harp4162')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		url = '/dataserver2/Objects/%s/CourseInvitations' % course_ntiid
		res = self.testapp.get(url, extra_environ=environ, status=200)

		assert_that(res.json_body, has_entry(ITEMS, has_length(1)))
		assert_that(res.json_body, has_entry(ITEMS, is_(["CLC3403"])))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_send_accept_invitation(self):
		with mock_dataserver.mock_db_trans(self.ds):
			user = self._create_user('ichigo')
			IUserProfile(user).email = 'ichigo@bleach.org'

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			invitiation = JoinCourseInvitation("CLC3403", self.entry_ntiid)
			component.getGlobalSiteManager().registerUtility(invitiation,
															 IJoinCourseInvitation,
															 "CLC3403")
			invitations = component.getUtility(IInvitations)
			invitations.registerInvitation(invitiation)

			entry = self.catalog_entry()
			course = ICourseInstance(entry)
			course_ntiid = to_external_ntiid_oid(course)

		mailer = component.getUtility(ITestMailDelivery)
		del mailer.queue[:]

		environ = self._make_extra_environ(username='harp4162')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		data = {'username':'ichigo', 'code':"CLC3403"}
		url = '/dataserver2/Objects/%s/SendCourseInvitations' % course_ntiid
		res = self.testapp.post_json(url, data, extra_environ=environ, status=200)
		assert_that(res.json_body, has_entry(ITEMS, has_length(1)))

		mailer = component.getUtility(ITestMailDelivery)
		msg = mailer.queue[0]

		html = decodestring(msg.html)
		to_check = '/dataserver2/users/ichigo/accept-course-invitations?code=CLC3403'
		assert_that(html, contains_string(to_check))

		environ = self._make_extra_environ(username='ichigo')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(to_check, extra_environ=environ, status=200)
		assert_that(res.json_body, has_entry('Class', u'CourseInstanceEnrollment'))
