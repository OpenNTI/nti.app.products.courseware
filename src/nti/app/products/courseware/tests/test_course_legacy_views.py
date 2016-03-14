#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import starts_with

import fudge

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._legacy_forums import AbstractMixin

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCreateForums(AbstractMixin, ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	testapp = None

	# This only works in the OU environment because that's where the purchasables are
	default_origin = str('http://janux.ou.edu')

	body_matcher = [not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-Open_Discussions.A_clc_discussion',
					not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-In_Class_Discussions.A_clc_discussion']

	open_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/Discussions/Open_Discussions/A_clc_discussion'
	default_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/Discussions/Forum'

	enrollment_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	def _extra_post_csv_create_forums(self):
		# We should have absolute NTIIDs for the containerid of posts in
		# new-style topics
		assert_that(self.comment_res.json_body['ContainerId'],
					 starts_with('tag:nextthought.com,2011-10:unknown-OID-0x'))

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	@fudge.patch('nti.contenttypes.courses.catalog.CourseCatalogEntry.isCourseCurrentlyActive')
	def test_create_topic_directly(self, fake_active):
		# make it look like the course is in session
		fake_active.is_callable().returns(True)

		inst_env = self._make_extra_environ(username='harp4162')

		topic_res = self.testapp.post_json(self.default_path,
										   { 'Class': 'Post',
											 'title': 'My New Blog',
											 'description': "This is a description of the thing I'm creating",
											 'body': ['My first thought'] },
										   status=201,
										   extra_environ=inst_env)
		assert_that(topic_res.json_body,
					# notability depends on mimetype
					has_entry('MimeType', "application/vnd.nextthought.forums.communityheadlinetopic"))
		assert_that(topic_res.json_body,
					has_entry('NTIID',
							  starts_with('tag:nextthought.com,2011-10:unknown-OID-0x')))
		assert_that(topic_res.json_body,
					has_entry('ContainerId',
							  starts_with('tag:nextthought.com,2011-10:unknown-OID-0x')))

		# It is notable to a student...
		enrolled_course_id = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
		self.post_user_data(enrolled_course_id,
							extra_path='/Courses/EnrolledCourses',
							status=201)
		res = self.fetch_user_recursive_notable_ugd()
		assert_that(res.json_body, has_entry('TotalItemCount', 0))

		# ... but only once its published
		self.testapp.post(self.require_link_href_with_rel(topic_res.json_body, 'publish'),
						  extra_environ=inst_env)
		res = self.fetch_user_recursive_notable_ugd()
		assert_that(res.json_body, has_entry('TotalItemCount', 1))

class TestCreateForumsOpenOnly(TestCreateForums):

	layer = PersistentInstructedCourseApplicationTestLayer

	testapp = None

	# XXX: All three, because the in-class discussions still created, but not the topic
	body_matcher = TestCreateForums.body_matcher[:3]

	scope = str('Open')
