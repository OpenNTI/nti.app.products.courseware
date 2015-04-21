#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
does_not = is_not

import fudge

from zope import component

from nti.app.products.courseware.discussions import _extract_content
from nti.app.products.courseware.discussions import discussions_forums
from nti.app.products.courseware.discussions import announcements_forums

from nti.contentfragments.interfaces import SanitizedHTMLContentFragment

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.dataserver.contenttypes.media import EmbeddedVideo 

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestDiscussions(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer

	contents = """
	This is the contents.
	Of the headline post

	Notice --- it has leading and trailing spaces, and even
	commas and blank lines. You can\u2019t ignore the special apostrophe.""".encode('windows-1252')

	mac_contents = contents.replace(b'\n', b'\r')
	
	default_origin = b'http://janux.ou.edu'
	
	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	
	vendor_info = {
		"NTI": {
			"Forums": {
				"AutoCreate":True,
			    "HasInClassDiscussions": True,
			    "HasOpenDiscussions": True
			},
		}
	}
				
	@classmethod
	def catalog_entry(self):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid == self.course_ntiid:
				return entry
			
	def test_extract_content_simple(self):
		content = _extract_content((self.contents, '[ntivideo][kaltura]kaltura://1500101/1_vkxo2g66/'))
		assert_that(content, is_(not_none()))
		assert_that(content, has_length(2))
		assert_that(content[0], does_not(contains_string('\r')))
		assert_that(content[0], has_length(168))
		assert_that(content[1], is_(EmbeddedVideo))

	def test_extract_content_mac(self):
		content = _extract_content((self.mac_contents, '[ntivideo]kaltura://1500101/1_vkxo2g66/'))
		assert_that(content, is_(not_none()))
		assert_that(content, has_length(2))
		assert_that(content[0], does_not(contains_string('\r')))
		assert_that(content[0], has_length(168))
		assert_that(content[1], is_(EmbeddedVideo))

	@fudge.patch('nti.app.products.courseware.discussions.get_vendor_info')
	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_discussion_creation(self, mock_gvi):
		discussion = CourseDiscussion()
		content = _extract_content(self.contents)[0]
		discussion.body = (SanitizedHTMLContentFragment(content),)
		discussion.scopes = (ES_ALL,)
		discussion.id = discussion.title = u'foo'
		
		mock_gvi.is_callable().with_args().returns(self.vendor_info)
		
		with mock_dataserver.mock_db_trans(self.ds,  site_name='platform.ou.edu'):
			entry = self.catalog_entry()
			course = ICourseInstance(entry)
			discussions = ICourseDiscussions(course)
			discussions['foo'] = discussion
			
			assert_that(discussions_forums(course), has_length(2))
			assert_that(announcements_forums(course), has_length(0))
