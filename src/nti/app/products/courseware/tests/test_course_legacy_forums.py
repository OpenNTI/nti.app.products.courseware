#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import LegacyInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._forums import _AbstractMixin

class TestCreateLegacyForums(_AbstractMixin, ApplicationLayerTest):
	
	layer = LegacyInstructedCourseApplicationTestLayer

	testapp = None

	# This only works in the OU environment because that's where the purchasables are
	default_origin = str('http://janux.ou.edu')

	body_matcher = ['tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-Open_Discussions',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-Open_Discussions.A_clc_discussion',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-In_Class_Discussions',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-In_Class_Discussions.A_clc_discussion']

	open_forum_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/'
	open_topic_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/A_clc_discussion'
	open_path = open_topic_path

class TestCreateLegacyForumsOpenOnly(TestCreateLegacyForums):

	layer = LegacyInstructedCourseApplicationTestLayer
	testapp = None
	body_matcher = TestCreateLegacyForums.body_matcher[:3]  # All three, because the in-class discussions still created, but not the topic
	scope = str('Open')
