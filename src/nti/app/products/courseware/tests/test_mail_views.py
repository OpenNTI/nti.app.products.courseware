#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import contains_string
does_not = is_not

from quopri import decodestring

from zope import component

from nti.app.mail.interfaces import Email

from nti.app.products.courseware import VIEW_COURSE_MAIL

from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.testing import ITestMailDelivery

from nti.dataserver.tests import mock_dataserver

open_name = u'aaa_nextthought_com'
credit_name = u'credit_nextthought_com'
open_address = u'open@nextthought.com'
credit_address = u'credit@nextthought.com'


class TestMailViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer
    testapp = None

    default_origin = 'http://janux.ou.edu'
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    from_address = u'janux@ou.edu'
    no_reply = u'no-reply@nextthought.com'
    external_reply_to = u'jzuech3@gmail.com'

    def _do_enroll(self):
        # Set up enrollments/nextthought email addresses.
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            open_user = User.get_user(open_name)
            course = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(course)
            IUserProfile(open_user).email_verified = True
            IUserProfile(open_user).email = open_address
            manager = ICourseEnrollmentManager(course)
            # Purchased falls in Open category
            manager.enroll(open_user, scope=ES_PURCHASED)

            credit_user = User.get_user(credit_name)
            manager.enroll(credit_user, scope=ES_CREDIT_DEGREE)
            IUserProfile(credit_user).email_verified = True
            IUserProfile(credit_user).email = credit_address

            user = User.get_user('harp4162')
            IUserProfile(user).email_verified = True
            IUserProfile(user).email = self.external_reply_to

            other_instructor = User.get_user('jmadden')
            profile = IUserProfile(other_instructor)
            profile.email_verified = True
            profile.email = u'zachary.roux@nextthought.com'

    def _get_messages(self, mailer, has_copy=False):
        """
        Validate we always have an author copy, returning the rest. Clear out
        our queue on the fly. If `has_copy` is False, we do not expect a
        instructor copy.
        """
        author_message = None
        results = []
        for msg in mailer.queue:
            if msg.get('To') == self.external_reply_to:
                author_message = msg
            else:
                results.append(msg)
        if has_copy:
            assert_that(author_message, not_none())
            assert_that(author_message.get('Subject'), contains_string('COPY'))
        else:
            assert_that(author_message, none())
        del mailer.queue[:]
        return results

    def _test_mail_payload(self, mail, reply_to_mail, instructor_env, link):
        """
        Validate address and body properties of emails sent to an individual
        open student.
        """
        # Test basic text
        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]
        self.testapp.post_json(link, mail, extra_environ=instructor_env)

        to_check = mail.get('Body')
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(1))
        msg = messages[0]
        assert_that(msg, has_property('body'))
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(msg, has_property('html'))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.no_reply))
        assert_that(msg.get('From'), contains_string(self.from_address))
        assert_that(msg.get('To'), is_(open_address))

        # Test encoding
        mail['Body'] = u'哈哈....Zürich is a hub'
        self.testapp.post_json(link, mail, extra_environ=instructor_env)

        to_check = mail.get('Body').encode('utf-8')
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(1))
        msg = messages[0]
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.no_reply))
        assert_that(msg.get('From'), contains_string(self.from_address))
        assert_that(msg.get('To'), is_(open_address))

        # Test html
        mail['Body'] = u'Test <br /> <br /> with line breaks. <br />'
        self.testapp.post_json(link, mail, extra_environ=instructor_env)

        to_check = u'with line breaks.'
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(1))
        msg = messages[0]
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(body, does_not(contains_string('<br>')))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(html, contains_string('Test <br>'))
        assert_that(msg.get('Reply-To'), is_(self.no_reply))
        assert_that(msg.get('From'), contains_string(self.from_address))
        assert_that(msg.get('To'), is_(open_address))

        # Test script w/external reply-to
        to_check = u'test output'
        script = u'<script><p>should be ignored</p> Other stuff.</script>'
        reply_to_mail['Body'] = u'<div>%s<p>%s</p></div>' % (script, to_check)
        self.testapp.post_json(link, reply_to_mail,
                               extra_environ=instructor_env)

        messages = self._get_messages(mailer)
        assert_that(messages, has_length(1))
        msg = messages[0]
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(body, does_not(contains_string('</p>')))
        assert_that(body, does_not(contains_string(script)))
        html = decodestring(msg.html)
        assert_that(html, contains_string('test output</p>'))
        assert_that(html, does_not(contains_string(script)))

        # Distinct reply-to and from headers; reply-to is external email addr.
        assert_that(msg.get('Reply-To'), is_(self.external_reply_to))
        assert_that(msg.get('From'), contains_string(self.from_address))
        assert_that(msg.get('To'), is_(open_address))

        # Test newlines with default subject.
        text_with_newlines = u"""IE11/win. 8.1\n\n\n1. In roster\n2. In the all students
                                view\n3. All Students, Allow replies from open, send a
                                copy\n\n\nfrom kaley\n"""

        reply_to_mail['Body'] = text_with_newlines
        reply_to_mail.pop('Subject')
        self.testapp.post_json(link, reply_to_mail,
                               extra_environ=instructor_env)

        messages = self._get_messages(mailer)
        assert_that(messages, has_length(1))
        msg = messages[0]
        assert_that(msg.get('Subject'), is_('Email from harp4162'))

    @WithSharedApplicationMockDS(users=(open_name, credit_name),
                                 testapp=True,
                                 default_authenticate=True)
    def test_roster_email(self):
        body = 'This is the email text body.'
        subject = 'Email Subject'
        mail = {'MimeType': Email.mime_type,
                'Body': body,
                'Subject': subject,
                'NoReply': True,
                'Copy': True}

        # Test mail without subject, with a reply address, and no copy.
        mail_with_reply = dict(mail)
        mail_with_reply['NoReply'] = False
        mail_with_reply['Subject'] = None
        mail_with_reply['Copy'] = False

        self._do_enroll()
        instructor_env = self._make_extra_environ('harp4162')
        res = self.testapp.get('/dataserver2/users/harp4162/Courses/AdministeredCourses',
                               extra_environ=instructor_env)

        role = res.json_body['Items'][0]

        res = self.testapp.get(self.require_link_href_with_rel(role, 'CourseInstance'),
                               extra_environ=instructor_env)

        course_instance = res.json_body
        roster_link = self.require_link_href_with_rel(course_instance,
                                                      'CourseEnrollmentRoster')
        email_link = self.require_link_href_with_rel(course_instance,
                                                     VIEW_COURSE_MAIL)

        # Mail student
        res = self.testapp.get(roster_link,
                               extra_environ=instructor_env)
        for enroll_record in res.json_body['Items']:
            roster_link = self.require_link_href_with_rel(enroll_record,
                                                          VIEW_COURSE_MAIL)
            self.testapp.post_json(roster_link, mail,
                                   extra_environ=instructor_env)
            self.testapp.post_json(roster_link, mail_with_reply,
                                   extra_environ=instructor_env)
            if enroll_record.get('Username') == open_name:
                open_email_link = roster_link

        # Mail everyone in course
        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]
        self.testapp.post_json(email_link, mail, extra_environ=instructor_env)
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(2))
        assert_that(messages[0].get('Reply-To'), is_(self.no_reply))
        assert_that(messages[1].get('Reply-To'), is_(self.no_reply))

        # Mail everyone with reply
        self.testapp.post_json(email_link, mail_with_reply,
                               extra_environ=instructor_env)
        messages = self._get_messages(mailer)
        assert_that(messages, has_length(2))
        assert_that(messages[0].get('Reply-To'), is_(self.external_reply_to))
        assert_that(messages[1].get('Reply-To'), is_(self.external_reply_to))

        # Mail everyone with replyToScope ForCredit
        self.testapp.post_json(email_link + '?replyToScope=ForCredit',
                               mail_with_reply, extra_environ=instructor_env)
        messages = self._get_messages(mailer)
        assert_that(messages, has_length(2))
        open_msg = messages[0] if messages[0].get('To') == open_address else messages[1]
        credit_msg = messages[0] if messages[0].get('To') == credit_address else messages[1]
        assert_that(open_msg.get('Reply-To'), is_(self.no_reply))
        assert_that(credit_msg.get('Reply-To'), is_(self.external_reply_to))

        # Test mailing an instructor along with the students in the course
        self.testapp.post_json(email_link + '?include-instructors=True',
                               mail, extra_environ=instructor_env)
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(3))
        assert_that(messages,
                    has_item(has_entry('To', 'zachary.roux@nextthought.com')))
        assert_that(messages,
                    is_not(has_item(has_entry('To', 'jzuech3@gmail.com'))))
        # Another instructor in the course should still have a reply-to address
        # even when students don't.
        assert_that(messages,
                    has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'zachary.roux@nextthought.com')))
        assert_that(messages,
                    is_not(has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'open@nextthought.com'))))
        assert_that(messages,
                    is_not(has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'credit@nextthought.com'))))

        self.testapp.post_json(email_link + '?include-instructors=True',
                               mail_with_reply, extra_environ=instructor_env)
        messages = self._get_messages(mailer, has_copy=False)
        assert_that(messages, has_length(3))
        assert_that(messages,
                    has_item(has_entry('To', 'zachary.roux@nextthought.com')))
        assert_that(messages,
                    is_not(has_item(has_entry('To', 'jzuech3@gmail.com'))))
        # The message to another instructor should also have a reply-to address
        # from the sender
        assert_that(messages,
                    has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'zachary.roux@nextthought.com')))
        assert_that(messages,
                    has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'open@nextthought.com')))
        assert_that(messages,
                    has_item(has_entries('Reply-To', 'jzuech3@gmail.com', 'To', 'credit@nextthought.com')))

        # Mail everyone with replyToScope open (also purchased)
        self.testapp.post_json(email_link + '?replyToScope=opEN',
                               mail_with_reply, extra_environ=instructor_env)
        messages = self._get_messages(mailer)
        assert_that(messages, has_length(2))
        open_msg = messages[0] if messages[0].get('To') == open_address else messages[1]
        credit_msg = messages[0] if messages[0].get('To') == credit_address else messages[1]
        assert_that(open_msg.get('Reply-To'), is_(self.external_reply_to))
        assert_that(credit_msg.get('Reply-To'), is_(self.no_reply))

        # Mail just for-credit
        self.testapp.post_json(email_link + '?scope=forCREDit',
                               mail_with_reply, extra_environ=instructor_env)
        messages = self._get_messages(mailer)
        assert_that(messages, has_length(1))
        assert_that(messages[0].get('To'), is_(credit_address))

        # Mail just public
        self.testapp.post_json(email_link + '?scope=public',
                               mail_with_reply, extra_environ=instructor_env)
        messages = self._get_messages(mailer)
        assert_that(messages, has_length(1))
        assert_that(messages[0].get('To'), is_(open_address))

        # 403s/404s
        self.testapp.post_json(email_link, mail, status=403)
        self.testapp.get(roster_link + '/not_enrolled/Mail',
                         status=404,
                         extra_environ=instructor_env)

        self._test_mail_payload(mail, mail_with_reply,
                                instructor_env, open_email_link)

    @WithSharedApplicationMockDS(users=(open_name, credit_name),
                                 testapp=True,
                                 default_authenticate=True)
    def test_emailing_student_with_instructor_copies(self):
        body = 'This is the email text body.'
        subject = 'Email Subject'
        mail = {'MimeType': Email.mime_type,
                'Body': body,
                'Subject': subject,
                'NoReply': True,
                'Copy': True}

        # Test mail with a reply address
        mail_with_reply = dict(mail)
        mail_with_reply['NoReply'] = False

        self._do_enroll()
        instructor_env = self._make_extra_environ('harp4162')
        res = self.testapp.get('/dataserver2/users/harp4162/Courses/AdministeredCourses',
                               extra_environ=instructor_env)

        role = res.json_body['Items'][0]

        course_href = self.require_link_href_with_rel(role, 'CourseInstance')
        course_instance = self.testapp.get(course_href, extra_environ=instructor_env).json_body

        roster_link = self.require_link_href_with_rel(
            course_instance, 'CourseEnrollmentRoster')
        self.require_link_href_with_rel(course_instance, VIEW_COURSE_MAIL)

        # Mail an open student
        res = self.testapp.get(roster_link,
                               extra_environ=instructor_env)
        for enroll_record in res.json_body['Items']:
            roster_link = self.require_link_href_with_rel(enroll_record,
                                                          VIEW_COURSE_MAIL)
            self.testapp.post_json(roster_link, mail,
                                   extra_environ=instructor_env)
            self.testapp.post_json(roster_link, mail_with_reply,
                                   extra_environ=instructor_env)
            if enroll_record.get('Username') == open_name:
                open_email_link = roster_link

        # Test emailing a student with no reply
        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]
        self.testapp.post_json(open_email_link + '?include-instructors=True',
                               mail, extra_environ=instructor_env)

        to_check = mail.get('Body')
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(2))

        msg = messages[0]
        assert_that(msg, has_property('body'))
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(msg, has_property('html'))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.no_reply))
        assert_that(msg.get('From'), contains_string('janux+'))
        assert_that(msg.get('From'), contains_string('@ou.edu'))
        assert_that(msg.get('To'), is_(open_address))

        msg = messages[1]
        assert_that(msg, has_property('body'))
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(msg, has_property('html'))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.external_reply_to))
        assert_that(msg.get('From'), contains_string('janux+'))
        assert_that(msg.get('From'), contains_string('@ou.edu'))
        assert_that(msg.get('To'), is_('zachary.roux@nextthought.com'))

        # Test emailing a student with replies enabled
        mailer = component.getUtility(ITestMailDelivery)
        del mailer.queue[:]
        self.testapp.post_json(open_email_link + '?include-instructors=True',
                               mail_with_reply, extra_environ=instructor_env)

        to_check = mail.get('Body')
        messages = self._get_messages(mailer, has_copy=True)
        assert_that(messages, has_length(2))

        msg = messages[0]
        assert_that(msg, has_property('body'))
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(msg, has_property('html'))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.external_reply_to))
        assert_that(msg.get('From'), contains_string('janux+'))
        assert_that(msg.get('From'), contains_string('@ou.edu'))
        assert_that(msg.get('To'), is_(open_address))

        msg = messages[1]
        assert_that(msg, has_property('body'))
        body = decodestring(msg.body)
        assert_that(body, contains_string(to_check))
        assert_that(msg, has_property('html'))
        html = decodestring(msg.html)
        assert_that(html, contains_string(to_check))
        assert_that(msg.get('Reply-To'), is_(self.external_reply_to))
        assert_that(msg.get('From'), contains_string('janux+'))
        assert_that(msg.get('From'), contains_string('@ou.edu'))
        assert_that(msg.get('To'), is_('zachary.roux@nextthought.com'))
