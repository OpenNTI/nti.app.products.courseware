#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import datetime

from tempfile import NamedTemporaryFile

from unittest import TestCase

import fudge

from PIL import Image

from hamcrest import calling
from hamcrest import contains
from hamcrest import is_
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import matches_regexp
from hamcrest import raises
does_not = is_not

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.subscribers import completion_context_default_policy

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.app.products.courseware.completion.utils import has_completed_course
from nti.app.products.courseware.completion.utils import ImageUtils
from nti.app.products.courseware.completion.utils import RetriesExceededError


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


class TestImageUtils(TestCase):

    def _test_convert(self,
                      subprocess_call,
                      density=None,
                      img_format=None):
        captured_args = []

        def capturing_call(*args, **_kwargs):
            captured_args.extend(args)
            return 0

        kwargs = {key: value for key, value in (('density', density),
                                                ('img_format', img_format))
                  if value is not None}

        subprocess_call.is_callable().calls(capturing_call)
        with ImageUtils() as utils:
            result = utils.convert("/a/b/c.svg",
                                   512, 256,
                                   **kwargs)

            expected_img_format = img_format or "png"
            assert_that(result, matches_regexp(r"c-.*\.%s"
                                               % expected_img_format))
            assert_that(captured_args[0], contains(
                "convert",
                "-density", str(density or "900"),
                "-background", "none",
                "-resize", matches_regexp("512.0*x256.0*"),
                "/a/b/c.svg",
                matches_regexp(r"%s:.*/c-.*\.%s"
                               % (expected_img_format,
                                  expected_img_format))
            ))

    @fudge.patch('nti.app.products.courseware.completion.utils._call',
                 'nti.app.products.courseware.completion.utils._get_size')
    def test_convert_success(self, subprocess_call, get_size):
        get_size.is_callable().returns(1)
        self._test_convert(subprocess_call)

    @fudge.patch('nti.app.products.courseware.completion.utils._call',
                 'nti.app.products.courseware.completion.utils._get_size')
    def test_convert_success_non_default(self, subprocess_call, get_size):
        get_size.is_callable().returns(1)
        self._test_convert(subprocess_call,
                           density=587,
                           img_format="jpeg")

    @fudge.patch('nti.app.products.courseware.completion.utils._call',
                 'nti.app.products.courseware.completion.utils._get_size')
    def test_convert_eventual_success(self, subprocess_call, get_size):
        get_size.is_callable()\
            .returns(0)\
            .next_call().returns(5)\
            .next_call().returns(1)
        self._test_convert(subprocess_call)

    @fudge.patch('nti.app.products.courseware.completion.utils._call',
                 'nti.app.products.courseware.completion.utils._get_size')
    def test_convert_failure(self, subprocess_call, get_size):
        get_size.is_callable().returns(0).times_called(6)
        assert_that(calling(self._test_convert).with_args(subprocess_call),
                            raises(RetriesExceededError))

    def test_constrain(self):
        with ImageUtils() as utils:
            with NamedTemporaryFile(delete=False, suffix=".png") as input_file:
                with Image.new('RGB', (10, 20), color='green') as image:
                    image.save(input_file)

                input_file = input_file.name

            filename = utils.constrain_size(input_file, 10, 10)

            with Image.open(filename) as image:
                assert_that(image.width, is_(5))
                assert_that(image.height, is_(10))