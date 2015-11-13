#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entry
from hamcrest import assert_that

import anyjson as json

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestCourseUGDViews(ApplicationLayerTest):
	"""
	We expect to be able to post UGD to a 'Pages' link
	in the course and that the returned ugd will contain
	this course context.
	"""

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	container_ntiid = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.subsec:BOOK_Three_PART_1"

	course_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice'

	user_pages_href = '/dataserver2/users/sjohnson@nextthought.com/Pages'

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_ugd(self):
		course = self.testapp.get(self.course_href)
		course_json = course.json_body

		# For our law course, get the pages href and the course ntiid
		course_links = course_json.get('Links')
		for link in course_links:
			if link.get('rel') == 'Pages':
				pages_href = link.get('href')
		course_ntiid = course_json.get('NTIID')

		data = json.serialize({ 'Class': 'Highlight', 'MimeType': 'application/vnd.nextthought.highlight',
								'ContainerId': self.container_ntiid,
								'selectedText': "This is the selected text",
								'applicableRange': {'Class': 'ContentRangeDescription'}})

		self.testapp.post(pages_href, data, status=201)

		user_ugd_path = self.user_pages_href + '(' + self.container_ntiid + ')/UserGeneratedData'
		user_ugd = self.testapp.get(user_ugd_path)
		user_ugd = user_ugd.json_body
		highlight_json = user_ugd.get('Items')[0]
		assert_that(highlight_json, has_entry('ContainerContext', course_ntiid))
