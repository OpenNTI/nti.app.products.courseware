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

import fudge
import unittest

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

QUIZ = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:QUIZ_01.01"
QUESTION = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.qid.aristotle.1"
VIDEO = 'tag:nextthought.com,2011-10:OU-NTIVideo-CLC3403_LawAndJustice.ntivideo.video_01.01'
READING = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:04.01_RequiredReading'
SUB_SECTION = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.subsec:BOOK_5_CHAPTER_3'
CARD = 'tag:nextthought.com,2011-10:OU-NTICard-CLC3403_LawAndJustice.nticard.nticard_RR_PDF_03.02'

COURSE_NTIID = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

class MockCatalog(object):

	containers = (COURSE_NTIID,)

	def get_containers(self, _):
		return self.containers

class TestPathLookup(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	def _do_path_lookup_video(self):
		# Video
		path = '/dataserver2/LibraryPath?objectId=%s' % VIDEO
		res = self.testapp.get(path)
		res = res.json_body

		assert_that(res, has_length(1))
		res = res[0]
		assert_that(res, has_length(2))
		assert_that(res[0], has_entry('Class', 'CourseInstance'))
		assert_that(res[1], has_entries('Class', 'PageInfo',
										'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
										'Title', '1. Defining Law and Justice'))

	def _check_catalog(self, res):
		assert_that(res, has_length(1))
		items = res.get( 'Items' )
		assert_that(items, has_length( 2 ))
		assert_that(items[0], has_entry('Class', 'CourseCatalogLegacyEntry'))
		assert_that(items[1], has_entry('Class', 'CourseCatalogLegacyEntry'))

	def _do_path_lookup(self, is_legacy=False, expected_status=200 ):
		# For legacy non-indexed, we only get one possible path.
		result_expected_val = 1 if is_legacy else 3

		# Get reading
		path = '/dataserver2/LibraryPath?objectId=%s' % READING
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		# No LessonOverview registered, so we lose outline.
		# We do get course followed by appropriate page info.
		if expected_status == 403:
			self._check_catalog(res)
		else:
			assert_that(res, has_length(result_expected_val))
			res = res[0]
			assert_that(res, has_length(2))
			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'PageInfo',
											'NTIID', READING,
											'Title', '4.1 Homicide Law of Draco'))

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

		# Quiz
		path = '/dataserver2/LibraryPath?objectId=%s' % QUIZ
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
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:QUIZ_01.01',
											'Title', 'Self-Quiz 1'))

		# Question (returns same)
		# Not found in legacy, not even catalog.
		status = 403 if is_legacy else expected_status
		path = '/dataserver2/LibraryPath?objectId=%s' % QUESTION
		res = self.testapp.get(path, status=status)
		if status != 403:
			res = res.json_body
			if expected_status == 403:
				self._check_catalog(res)
			else:
				assert_that(res, has_length(result_expected_val))
				res = res[0]
				assert_that(res, has_length(2))

				assert_that(res[0], has_entry('Class', 'CourseInstance'))
				assert_that(res[1], has_entries('Class', 'PageInfo',
												'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:QUIZ_01.01',
												'Title', 'Self-Quiz 1'))

		# Card
		path = '/dataserver2/LibraryPath?objectId=%s' % CARD
		res = self.testapp.get(path, status=expected_status)
		res = res.json_body

		# Cards are not indexed in our container catalog, so
		# we go down the legacy path that only returns one result.
		if expected_status == 403:
			self._check_catalog(res)
		else:
			assert_that(res, has_length(1))
			res = res[0]
			assert_that(res, has_length(2))

			assert_that(res[0], has_entry('Class', 'CourseInstance'))
			assert_that(res[1], has_entries('Class', 'PageInfo',
											'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:03.02_RequiredReading',
											'Title', '3.2 Taplin, Shield of Achilles (within the Iliad)'))

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_catalog')
	@fudge.patch('nti.app.products.courseware.adapters._is_user_enrolled')
	def test_contained_path(self, mock_get_catalog, mock_enrolled):
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns(mock_catalog)
		mock_enrolled.is_callable().returns( True )
		self._do_path_lookup()

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_catalog')
	@fudge.patch('nti.app.products.courseware.adapters._is_user_enrolled')
	def test_contained_path_unenrolled(self, mock_get_catalog, mock_enrolled):
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns(mock_catalog)
		mock_enrolled.is_callable().returns( False )
		self._do_path_lookup( expected_status=403 )

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters._get_courses_from_container')
	@fudge.patch('nti.app.products.courseware.adapters._is_user_enrolled')
	def test_contained_path_legacy(self, mock_get_courses, mock_enrolled):
		"""
		Our library path to the given ntiid is returned,
		even though we do not have a catalog.
		"""
		mock_catalog = MockCatalog()
		mock_catalog.containers = []
		mock_get_courses.is_callable().returns( () )
		mock_enrolled.is_callable().returns( True )
		self._do_path_lookup( is_legacy=True )

	@unittest.expectedFailure
	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_catalog')
	def test_contained_path_video(self, mock_get_catalog):
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns(mock_catalog)
		self._do_path_lookup_video()
