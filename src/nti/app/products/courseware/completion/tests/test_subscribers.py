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
does_not = is_not

from quopri import decodestring

from zope import component
from zope import interface

from zope.event import notify

from nti.app.testing.testing import ITestMailDelivery

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import UserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import IRequiredCompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
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

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IUserProfile


@component.adapter(ICourseInstance)
@interface.implementer(IRequiredCompletableItemProvider)
class _MockRequiredItemProvider(object):

    def __init__(self, course):
        self.course = course

    def iter_items(self, unused_user):
        return (MockCompletableItem(u'tag:nextthought.com,2011-10:Test001'),)


class TestSubscribers(ApplicationLayerTest):

    def _completed_item(self, user, item, success):
        return CompletedItem(Item=item,
                             Principal=user,
                             CompletedDate=datetime.datetime.utcnow(),
                             Success=success)

    def _send_update(self, user, course):
        notify(UserProgressUpdatedEvent(obj=course,
                                        user=user,
                                        context=course))

    @WithMockDSTrans
    def test_completion_event(self):
        """
        Validate we fire a CourseCompletedEvent on certain conditions.
        """
        # Setup
        course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)
        entry = ICourseCatalogEntry(course, None)
        assert_that(entry, not_none())
        entry.ntiid = u'tag:nextthought.com,2011-10:TestCourseCompletionSubscriber001'
        assert_that(entry.ntiid, not_none())
        user = User.create_user(username=u'user001')
        item = MockCompletableItem(u'tag:nextthought.com,2011-10:Test001')

        self.subscriber_hit = False
        # Install subscriber
        @component.adapter(ICourseInstance, ICourseCompletedEvent)
        def course_completion_listener(subscriber_course, event):
            self.subscriber_hit = True
            assert_that(subscriber_course, is_(course))
            assert_that(event.user, is_(user))
            assert_that(event.context, is_(course))
        sm = component.getGlobalSiteManager()
        sm.registerHandler(course_completion_listener)
        sm.registerSubscriptionAdapter(_MockRequiredItemProvider)

        try:
            # No policy
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))

            # Policy with no progress
            policy = CompletableItemAggregateCompletionPolicy()
            policy.percentage = 1.0
            policy_container = ICompletionContextCompletionPolicyContainer(course)
            policy_container.context_policy = policy
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))

            # Course completed item, unsuccessful
            principal_container = component.queryMultiAdapter((user, course),
                                                              IPrincipalCompletedItemContainer)
            completed_item = self._completed_item(user, item, False)
            principal_container.add_completed_item(completed_item)
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))

            # Now successful but not enrolled
            completed_item.Success = True
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))
            self.subscriber_hit = False

            # Enrolled but unsuccessful
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
            completed_item.Success = False
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))
            self.subscriber_hit = False

            # Now enrolled and successful
            completed_item.Success = True
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(True))
            self.subscriber_hit = False

            # Another event does not fire
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(False))

            # Completed course, but unsuccessful will fire a new event
            assert_that(principal_container.ContextCompletedItem, not_none())
            principal_container.ContextCompletedItem.Success = False
            self._send_update(user, course)
            assert_that(self.subscriber_hit, is_(True))
        finally:
            sm.unregisterHandler(course_completion_listener)
            sm.unregisterSubscriptionAdapter(_MockRequiredItemProvider)

    @WithMockDSTrans
    def test_completion_email(self):
        """
        Validate we fire a CourseCompletedEvent on certain conditions.
        """
        # Setup
        course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)
        entry = ICourseCatalogEntry(course, None)
        assert_that(entry, not_none())
        entry.ntiid = u'tag:nextthought.com,2011-10:TestCourseCompletionSubscriber001'
        assert_that(entry.ntiid, not_none())
        user = User.create_user(username=u'user001_completion_email')
        IUserProfile(user).email = u'ichigo@bleach.org'
        enrollment_manager = ICourseEnrollmentManager(course)
        enrollment_manager.enroll(user)

        mailer = component.getUtility(ITestMailDelivery)
        def _get_mail_msg():
            assert_that(mailer.queue, has_length(1))
            msg = mailer.queue[0]
            assert_that(msg, has_property('body'))
            body = decodestring(msg.body)
            del mailer.queue[:]
            return body

        notify(CourseCompletedEvent(course, user))
        msg = _get_mail_msg()
        assert_that(msg, contains_string("Great job completing"))
        assert_that(msg, does_not(contains_string("Feel free to download")))

        # Policy with no cert
        policy = CompletableItemAggregateCompletionPolicy()
        policy.percentage = 1.0
        policy_container = ICompletionContextCompletionPolicyContainer(course)
        policy_container.context_policy = policy
        notify(CourseCompletedEvent(course, user))
        msg = _get_mail_msg()
        assert_that(msg, contains_string("Great job completing"))
        assert_that(msg, does_not(contains_string("Feel free to download")))

        policy.offers_completion_certificate = True
        notify(CourseCompletedEvent(course, user))
        msg = _get_mail_msg()
        assert_that(msg, contains_string("Great job completing"))
        assert_that(msg, contains_string("Feel free to download"))
