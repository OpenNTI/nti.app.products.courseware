#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import contains_inanyorder
does_not = is_not

import fudge

from zope import component

from nti.app.products.courseware.discussions import get_acl
from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import _extract_content
from nti.app.products.courseware.discussions import discussions_forums
from nti.app.products.courseware.discussions import create_course_forums
from nti.app.products.courseware.discussions import announcements_forums
from nti.app.products.courseware.discussions import get_forums_for_discussion

from nti.contentfragments.interfaces import SanitizedHTMLContentFragment

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.dataserver.contenttypes.media import EmbeddedVideo
from nti.dataserver.contenttypes.forums.forum import CommunityForum

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
	commas and blank lines. You can\u2019t ignore the special apostrophe."""

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
		assert_that(content[0], has_length(169))
		assert_that(content[1], is_(EmbeddedVideo))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	@fudge.patch('nti.app.products.courseware.discussions.get_vendor_info')
	def test_discussion_creation(self, mock_gvi):
		discussion = CourseDiscussion()
		content = _extract_content((self.contents,))[0]
		discussion.body = (SanitizedHTMLContentFragment(content),)
		discussion.scopes = (ES_ALL,)
		discussion.title = 'title'
		discussion.id = "%s://%s" % (NTI_COURSE_BUNDLE, 'foo')

		mock_gvi.is_callable().with_args().returns(self.vendor_info)

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = self.catalog_entry()
			course = ICourseInstance(entry)
			discussions = ICourseDiscussions(course)
			discussions['foo'] = discussion

			assert_that(discussions_forums(course), has_length(2))
			assert_that(announcements_forums(course), has_length(0))

			acl = get_acl(course)
			assert_that(acl , has_length(2))
			assert_that(acl[0].to_external_string() , is_(u'Allow:harp4162:All'))

			result = create_course_forums(course)
			assert_that(result , has_entry(u'discussions',
										   has_entries('ForCredit',
														contains_inanyorder(u'In_Class_Discussions',
																			is_(CommunityForum)),
													   'Public',
													   contains_inanyorder('Open_Discussions',
																			is_(CommunityForum)))))

			discussions = result['discussions']
			for t in discussions.values():
				_, forum = t
				assert_that(forum, has_property('__acl__', has_length(3)))
				assert_that(forum, has_property('__entities__', has_length(1)))

			result = create_topics(discussion)
			assert_that(result, has_item('tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-In_Class_Discussions._foo'))
			assert_that(result, has_item('tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-Open_Discussions._foo'))

			assert_that(forum, has_key('_foo'))

			f4ds = get_forums_for_discussion(discussion, course)
			assert_that(f4ds, has_length(2))
			forum = f4ds.get( 'Open_Discussions' )
			discussion_ntiid = tuple(forum.values())[0].NTIID
			forum_ntiid = forum.NTIID

		# Path lookup, not enrolled so we get the catalog entry
		# Forum -> (Course,Board)
		path = '/dataserver2/LibraryPath?objectId=%s' % forum_ntiid
		res = self.testapp.get( path, status=403 )
		res = res.json_body

		res = res.get( 'Items' )
		assert_that( res, has_length( 1 ))
		res = res[0]
		assert_that( res, has_entry( 'Class', 'CourseCatalogLegacyEntry' ))

		# Topic -> (Course,Board,Forum)
		path = '/dataserver2/LibraryPath?objectId=%s' % discussion_ntiid
		res = self.testapp.get( path, status=403 )
		res = res.json_body

		res = res.get( 'Items' )
		assert_that( res, has_length( 1 ))
		res = res[0]
		assert_that( res, has_entry( 'Class', 'CourseCatalogLegacyEntry' ))

# 		assert_that( res, has_length( 1 ))
# 		res = res[0]
# 		assert_that( res, has_length( 3 ))
#
# 		assert_that( res[0], has_entry( 'Class', 'CourseCatalogLegacyEntry' ))
# 		assert_that( res[1], has_entries( 'Class', 'CommunityBoard',
# 										'title', 'Discussions' ))
# 		assert_that( res[2], has_entries( 'Class', 'CommunityForum',
# 										'title', 'Open Discussions' ))
