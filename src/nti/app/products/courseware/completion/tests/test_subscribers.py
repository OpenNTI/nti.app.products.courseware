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
from hamcrest import assert_that
does_not = is_not

from zope import component
from zope import interface

from zope.event import notify

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
from nti.contenttypes.courses.interfaces import ICourseCompletedEvent

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


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

        # Now successful
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
