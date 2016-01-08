#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than_or_equal_to

import fudge

from zope import component

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import _extract_content
from nti.app.products.courseware.discussions import create_course_forums
from nti.app.products.courseware.discussions import get_forums_for_discussion

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.contenttypes.courses.discussions.model import CourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.contentfragments.interfaces import SanitizedHTMLContentFragment

from nti.dataserver.tests import mock_dataserver
from nti.dataserver.users import User

COURSE_NTIID = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

SUB_SECTION = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.subsec:BOOK_5_CHAPTER_3'
CARD = 'tag:nextthought.com,2011-10:OU-NTICard-CLC3403_LawAndJustice.nticard.nticard_RR_PDF_03.02'

READING = "tag:nextthought.com,2011-10:OU-RelatedWorkRef-CS1323_F_2015_Intro_to_Computer_Programming.relatedworkref.relwk:01.01_install_mac"
SLIDE_VIDEO = "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.02_Mac"
SLIDE_DECK = "tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_F_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac"

NON_ROLL_VIDEO = "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_02.01.01_Primative"

VIDEO_ROLL_VIDEO = "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_02.01.03_Cell_Phone"

QUESTION_SET = "tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.set.qset:Prj_1"
QUESTION = "tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.qid:Prj_1.1"

CS1323_PACKAGE = 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming'

class TestPathLookup(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	contents = """
	This is the contents.
	Of the headline post

	Notice --- it has leading and trailing spaces, and even
	commas and blank lines. You can\u2019t ignore the special apostrophe.
	"""

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
			if entry.ntiid == COURSE_NTIID:
				return entry

	@fudge.patch('nti.app.products.courseware.discussions.get_vendor_info')
	def _create_discussions(self, mock_gvi):
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
			create_course_forums(course)
			create_topics(discussion)

			f4ds = get_forums_for_discussion(discussion, course)
			assert_that(f4ds, has_length(2))
			forum = f4ds.get('Open_Discussions')
			self.discussion_ntiid = tuple(forum.values())[0].NTIID
			self.forum_ntiid = forum.NTIID

	def _check_catalog(self, res, res_count=1):
		items = res.get('Items')
		assert_that(items, has_length(greater_than_or_equal_to(res_count)))
		for item in items:
			assert_that(item, has_entry('Class', 'CourseCatalogLegacyEntry'))

	def _do_cs1323_path_lookup(self, is_legacy=False, expected_status=200):
		# For legacy non-indexed, we only get one possible path.
		result_expected_val = 1

		# Video
		path = '/dataserver2/LibraryPath?objectId=%s' % NON_ROLL_VIDEO
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		# TODO: CS1323 only seems to resolve to the package, the units themselves do not contain
		# these object ids. It's probably because this video is contained in a video roll,
		# and the slide is contained within a slide deck.
		page_info = CS1323_PACKAGE if is_legacy else 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:02.01_LESSON'

		if expected_status == 403:
			self._check_catalog(res, res_count=1)
		else:
			assert_that(res, has_length(result_expected_val))
			res = res[0]
			assert_that( res, has_length( 4 ))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
											'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.3.0'))
			assert_that(res[2], has_entries('Class', 'Video',
											'NTIID', NON_ROLL_VIDEO))
			assert_that(res[3], has_entries('Class', 'PageInfo',
											'NTIID', page_info))

		# Get reading
		path = '/dataserver2/LibraryPath?objectId=%s' % READING
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		if expected_status == 403:
			self._check_catalog(res, res_count=1)
		else:
			assert_that(res, has_length(result_expected_val))
			res = res[0]
			assert_that( res, has_length( 4 ))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
											'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.0.1'))
			assert_that(res[2], has_entries('Class', 'RelatedWork',
											'NTIID', READING))
			assert_that(res[3], has_entries('Class', 'PageInfo',
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.03_LESSON' ))

		# Quiz
		path = '/dataserver2/LibraryPath?objectId=%s' % QUESTION_SET
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body
		if expected_status == 403:
			self._check_catalog(res)
		else:
			assert_that(res, has_length(result_expected_val))
			res = res[0]
			assert_that(res, has_length(4))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
											'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.2.1'))
			assert_that(res[2], has_entries('Class', 'AssignmentRef',
											'NTIID', 'tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:Project_1'))
			assert_that(res[3], has_entries('Class', 'PageInfo',
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.project_1_(100_points)'))

		# Question (returns same)
		# Not found in legacy, not even catalog.
		status = 403 if is_legacy else expected_status
		path = '/dataserver2/LibraryPath?objectId=%s' % QUESTION
		res = self.testapp.get(path, status=status)
		if not is_legacy:
			res = res.json_body
			if expected_status == 403:
				self._check_catalog(res)
			else:
				assert_that(res, has_length(result_expected_val))
				res = res[0]
				assert_that(res, has_length(4))

				assert_that(res[0], has_entry('Class', 'CourseInstance'))
				assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
												'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.2.1'))
				assert_that(res[2], has_entries('Class', 'AssignmentRef',
												'NTIID', 'tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:Project_1'))
				assert_that(res[3], has_entries('Class', 'PageInfo',
												'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.project_1_(100_points)'))

		# Slide video
		path = '/dataserver2/LibraryPath?objectId=%s' % SLIDE_VIDEO
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		page_info = CS1323_PACKAGE if is_legacy else 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.03_LESSON'

		if expected_status == 403:
			self._check_catalog(res, res_count=2)
		else:
			assert_that(res, has_length(1))
			res = res[0]
			assert_that(res, has_length(5))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
											'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.0.1'))
			assert_that(res[2], has_entries('Class', 'NTISlideDeck',
											'NTIID', SLIDE_DECK))
			assert_that(res[3], has_entries('Class', 'Video',
											'NTIID', SLIDE_VIDEO))
			assert_that(res[4], has_entries('Class', 'PageInfo',
											'NTIID', page_info))

		# SlideDeck
		path = '/dataserver2/LibraryPath?objectId=%s' % SLIDE_DECK
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		if expected_status == 403:
			self._check_catalog(res, res_count=2)
		else:
			assert_that(res, has_length(1))
			res = res[0]
			assert_that(res, has_length(5))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'CourseOutlineContentNode',
											'NTIID', 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.0.1'))
			assert_that(res[2], has_entries('Class', 'NTISlideDeck',
											'NTIID', SLIDE_DECK))
			assert_that(res[3], has_entries('Class', 'Video',
											'NTIID', SLIDE_VIDEO))
			assert_that(res[4], has_entries('Class', 'PageInfo',
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.03_LESSON'))

	def _do_clc_path_lookup(self, expected_status=200):
		self._create_discussions()

		# For legacy non-indexed, we only get one possible path.
		result_expected_val = 1

		# Forums: Course/Board
		obj_path = '/dataserver2/Objects/%s/LibraryPath' % self.forum_ntiid
		gen_path = '/dataserver2/LibraryPath?objectId=%s' % self.forum_ntiid
		for path in (obj_path, gen_path):
			res = self.testapp.get(path, status=expected_status)
			res = res.json_body

			if expected_status == 403:
				# Course specific forum/topic: only single catalog
				self._check_catalog(res)
			else:
				assert_that(res, has_length(1))
				res = res[0]
				assert_that(res, has_length(2))

				assert_that(res[0], has_entry('Class', 'CourseInstance'))
				assert_that(res[1], has_entries('Class', 'CommunityBoard',
												'title', 'Discussions'))

		# Topic: Course/Board/Forum
		obj_path = '/dataserver2/Objects/%s/LibraryPath' % self.discussion_ntiid
		gen_path = '/dataserver2/LibraryPath?objectId=%s' % self.discussion_ntiid
		for path in (obj_path, gen_path):
			res = self.testapp.get(path, status=expected_status)
			res = res.json_body

			if expected_status == 403:
				self._check_catalog(res)
			else:
				assert_that(res, has_length(1))
				res = res[0]
				assert_that(res, has_length(3))

				assert_that(res[0], has_entry('Class', 'CourseInstance'))
				assert_that(res[1], has_entries('Class', 'CommunityBoard',
												'title', 'Discussions'))
				assert_that(res[2], has_entries('Class', 'CommunityForum',
												'title', 'Open Discussions'))

		# Sub section
		path = '/dataserver2/LibraryPath?objectId=%s' % SUB_SECTION
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		if expected_status == 403:
			self._check_catalog(res)
		else:
			assert_that(res, has_length(result_expected_val))
			res = res[0]
			assert_that(res, has_length(2))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'PageInfo',
											# XXX Does this NTIID make sense?
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:01.01_RequiredReading',
											'Title', '1.1 Aristotle, Nicomachean Ethics, 5.3-5.8'))

		# Card
		path = '/dataserver2/LibraryPath?objectId=%s' % CARD
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		# Cards are not indexed in our container catalog, so
		# we go down the legacy path that only returns one result.
		if expected_status == 403:
			self._check_catalog(res, res_count=2)
		else:
			assert_that(res, has_length(1))
			res = res[0]
			assert_that(res, has_length(2))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'PageInfo',
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:03.02_RequiredReading',
											'Title', '3.2 Taplin, Shield of Achilles (within the Iliad)'))

	def _enroll(self):
		with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
			user = User.get_user('sjohnson@nextthought.com')

			cat = component.getUtility(ICourseCatalog)
			for group, bundle in (( 'Fall2013', 'CLC3403_LawAndJustice' ),
								  ( 'Fall2015', 'CS 1323' )):
				course = cat[group][bundle]
				manager = ICourseEnrollmentManager(course)
				manager.enroll(user, scope='ForCreditDegree')

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.contentlibrary.views.library_views._LibraryPathView._get_legacy_results',
				'nti.app.contentlibrary.adapters._get_bundles_from_container')
	def test_cs1323_contained_path(self, mock_legacy, mock_get_bundles):
		# CS1323 tests slides/videos/readings/self-assessments/video-rolls.
		# It has a full outline for these tests.
		self._enroll()
		mock_legacy.is_callable().returns(())
		mock_get_bundles.is_callable().returns(())
		self._do_cs1323_path_lookup()

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_library_catalog',
				'nti.app.contentlibrary.adapters._get_bundles_from_container')
	def test_clc_contained_path(self, mock_get_catalog, mock_get_bundles):
		# CLC tests subsections, cards, and discussions/forums (for convenience).
		# We do not have an outline for this course.
		class MockCatalog(object):
			containers = (COURSE_NTIID,)
			def get_containers(self, _):
				return self.containers

		# The test course we're using does not have an outline
		self._enroll()
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns(mock_catalog)
		mock_get_bundles.is_callable().returns(())
		self._do_clc_path_lookup()

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.contentlibrary.views.library_views._LibraryPathView._get_legacy_results',
				'nti.app.contentlibrary.adapters._get_bundles_from_container',
				'nti.app.products.courseware.adapters._is_catalog_entry_visible')
	def test_contained_path_unenrolled(self, mock_legacy, mock_get_bundles, mock_catalog_entry_visible):
		mock_legacy.is_callable().returns(())
		mock_get_bundles.is_callable().returns(())
		mock_catalog_entry_visible.is_callable().returns( True )
		self._do_cs1323_path_lookup(expected_status=403)

# TODO: test content editor
# TODO: test notes on content units (containing self-assessments etc)

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters._get_courses_from_container')
	@fudge.patch('nti.app.contentlibrary.adapters._get_bundles_from_container')
	@fudge.patch('nti.appserver.context_providers.get_hierarchy_context')
	def test_contained_path_legacy(self, mock_get_courses, mock_get_bundles, mock_get_context):
		"""
		Our library path to the given ntiid is returned,
		even though we do not have the index catalog.
		"""
		self._enroll()
		mock_get_courses.is_callable().returns(())
		mock_get_bundles.is_callable().returns(())
		mock_get_context.is_callable().returns(())
		self._do_cs1323_path_lookup(is_legacy=True)
		self._do_clc_path_lookup()
