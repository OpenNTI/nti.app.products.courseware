#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime

import fudge

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from zope import component

from zope.event import notify

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import UserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.subscribers import completion_context_default_policy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import CourseCompletedEvent
from nti.contenttypes.courses.interfaces import ICourseCompletedEvent

from nti.app.products.courseware.completion.utils import has_completed_course

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


class TestSubscribers(ApplicationLayerTest):

    def _completed_item(self, user, success):
        return CompletedItem(Item=MockCompletableItem(u'tag:nextthought.com,2011-10:Test001'),
                             Principal=user,
                             CompletedDate=datetime.datetime.utcnow(),
                             Success=success)

    def _send_update(self, user, course):
        notify(UserProgressUpdatedEvent(obj=course,
                                        user=user,
                                        context=course))

    @WithMockDSTrans
    def test_completion_event(self):
        # Setup
        course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(course)
        user = User.create_user(username=u'user001')

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
