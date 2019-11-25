#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime

import fudge

from hamcrest import is_
from hamcrest import is_not
from hamcrest import assert_that
does_not = is_not

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.subscribers import completion_context_default_policy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.app.products.courseware.completion.utils import has_completed_course

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dataserver.users import User


class TestUtils(ApplicationLayerTest):

    def _completed_item(self, user, success):
        return CompletedItem(Item=MockCompletableItem(u'tag:nextthought.com,2011-10:Test001'),
                             Principal=user,
                             CompletedDate=datetime.datetime.utcnow(),
                             Success=success)

    @WithMockDSTrans
    @fudge.patch('nti.contenttypes.completion.policies.CompletableItemAggregateCompletionPolicy.is_complete')
    def test_has_completed_course(self, mock_is_complete):
        user = User.create_user(username=u'user001')

        course = ContentCourseInstance()
        mock_dataserver.current_transaction.add(course)

        completion_context_default_policy(course)

        # not complete
        mock_is_complete.is_callable().returns(None)
        assert_that(has_completed_course(user, course), is_(False))
        assert_that(has_completed_course(user, course, success_only=True), is_(False))

        # complete but failed
        mock_is_complete.is_callable().returns(self._completed_item(user, False))
        assert_that(has_completed_course(user, course), is_(True))
        assert_that(has_completed_course(user, course, success_only=True), is_(False))

        # successfully completed
        mock_is_complete.is_callable().returns(self._completed_item(user, True))
        assert_that(has_completed_course(user, course), is_(True))
        assert_that(has_completed_course(user, course, success_only=True), is_(True))
