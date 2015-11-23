#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_string
does_not = is_not

from quopri import decodestring

from zope import component

from nti.app.mail.interfaces import Email

from nti.app.products.courseware import VIEW_COURSE_MAIL

from nti.app.testing.testing import ITestMailDelivery

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

import nti.dataserver.tests.mock_dataserver as mock_dataserver

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

class TestMailViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer
	testapp = None

	# XXX: This only works in the OU environment because that's where the purchasables are
	default_origin = b'http://janux.ou.edu'
	enrolled_courses_href = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
	expected_enrollment_href = '/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.course_info'


	def _test_mail_payload(self, mail, instructor_env, link):
		# Test basic text
		mailer = component.getUtility(ITestMailDelivery)
		del mailer.queue[:]
		self.testapp.post_json(link, mail, extra_environ=instructor_env)

		to_check = mail.get( 'Body' )
		assert_that( mailer.queue, has_length(1) )
		msg = mailer.queue[0]
		assert_that( msg, has_property( 'body'))
		body = decodestring(msg.body)
		assert_that( body, contains_string( to_check ) )
		assert_that( msg, has_property('html'))
		html = decodestring(msg.html)
		assert_that( html, contains_string( to_check ) )

		# Test encoding
		mail['Body'] = '哈哈....Zürich is a hub'
		del mailer.queue[:]
		self.testapp.post_json(link, mail, extra_environ=instructor_env)

		to_check = mail.get( 'Body' ).encode( 'utf-8' )
		assert_that( mailer.queue, has_length(1) )
		msg = mailer.queue[0]
		body = decodestring(msg.body)
		assert_that( body, contains_string( to_check ) )
		html = decodestring(msg.html)
		assert_that( html, contains_string( to_check ) )

		# Test html
		mail['Body'] = 'Test <br /> <br /> with line breaks. <br />'
		del mailer.queue[:]
		self.testapp.post_json(link, mail, extra_environ=instructor_env)

		to_check = 'with line breaks.'
		assert_that( mailer.queue, has_length(1) )
		msg = mailer.queue[0]
		body = decodestring(msg.body)
		assert_that( body, contains_string( to_check ) )
		assert_that( body, does_not( contains_string( '<br>' ) ) )
		html = decodestring(msg.html)
		assert_that( html, contains_string( to_check ) )
		assert_that( html, contains_string( 'Test <br>' ) )

		# Test script
		mail['Body'] = '<div><script><p>should be ignored</p> Other stuff.</script><p>test output</p>'
		del mailer.queue[:]
		self.testapp.post_json(link, mail, extra_environ=instructor_env)

		to_check = 'test output'
		script = '<script><p>should be ignored</p> Other stuff.</script>'
		assert_that( mailer.queue, has_length(1) )
		msg = mailer.queue[0]
		body = decodestring(msg.body)
		assert_that( body, contains_string( to_check ) )
		assert_that( body, does_not( contains_string( '</p>' ) ) )
		assert_that( body, does_not( contains_string( script ) ) )
		html = decodestring(msg.html)
		assert_that( html, contains_string( 'test output</p>' ) )
		assert_that( html, does_not( contains_string( script ) ) )

	@WithSharedApplicationMockDS(users=('aaa_nextthought_com',),
								 testapp=True,
								 default_authenticate=True)
	def test_roster_email(self):
		body = 'This is the email text body.'
		subject = 'Email Subject'
		mail = {'MimeType': Email.mime_type,
				'Body': body,
				'Subject': subject,
				'NoReply': True }

		# Test mail without subject and with a reply address.
		mail_with_reply = dict(mail)
		mail_with_reply['NoReply'] = False
		mail_with_reply['Subject'] = None

		instructor_env = self._make_extra_environ('harp4162')
		jmadden_environ = self._make_extra_environ(username='aaa_nextthought_com')

		# Give the user a NT email address.
		with mock_dataserver.mock_db_trans(self.ds):
			user = User.get_user('aaa_nextthought_com')
			IUserProfile(user).email_verified = True
			IUserProfile(user).email = 'bill@nextthought.com'

		res = self.testapp.get('/dataserver2/users/harp4162/Courses/AdministeredCourses',
								extra_environ=instructor_env)

		role = res.json_body['Items'][0]
		course_instance = role['CourseInstance']
		roster_link = self.require_link_href_with_rel(course_instance, 'CourseEnrollmentRoster')
		email_link = self.require_link_href_with_rel(course_instance, VIEW_COURSE_MAIL)

		# Put everyone in the roster
		self.testapp.post_json(self.enrolled_courses_href, 'CLC 3403', status=201)

		self.testapp.post_json('/dataserver2/users/aaa_nextthought_com/Courses/EnrolledCourses',
								'CLC 3403',
								extra_environ=jmadden_environ,
								status=201)

		# Mail student
		res = self.testapp.get(roster_link,
								extra_environ=instructor_env)
		for enroll_record in res.json_body['Items']:
			roster_link = self.require_link_href_with_rel(enroll_record, VIEW_COURSE_MAIL)
			self.testapp.post_json(roster_link, mail, extra_environ=instructor_env)
			self.testapp.post_json(roster_link, mail_with_reply, extra_environ=instructor_env)

		# Mail course
		self.testapp.post_json(email_link, mail, extra_environ=instructor_env)
		self.testapp.post_json(email_link, mail_with_reply, extra_environ=instructor_env)

		# 403s/404s
		self.testapp.post_json(email_link, mail, status=403)
		self.testapp.get(roster_link + '/not_enrolled/Mail',
						 status=404,
						 extra_environ=instructor_env)

		self._test_mail_payload( mail, instructor_env, email_link )
