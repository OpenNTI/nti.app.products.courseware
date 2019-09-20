#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.app.products.courseware.tests import LegacyInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._legacy_forums import AbstractMixin

from nti.app.testing.application_webtest import ApplicationLayerTest


class TestCreateLegacyForums(AbstractMixin, ApplicationLayerTest):

    layer = LegacyInstructedCourseApplicationTestLayer

    testapp = None

    # This only works in the OU environment because that's where the
    # purchasables are
    default_origin = 'http://janux.ou.edu'

    open_forum_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/'
    open_topic_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/A_clc_discussion'
    open_path = open_topic_path


class TestCreateLegacyForumsOpenOnly(TestCreateLegacyForums):

    layer = LegacyInstructedCourseApplicationTestLayer

    testapp = None

    # All three, because the in-class discussions still created, but not the
    # topic
    body_matcher = TestCreateLegacyForums.body_matcher[:3]
    scope = 'Open'
