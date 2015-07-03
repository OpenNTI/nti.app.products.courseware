#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

VIDEO = 'tag:nextthought.com,2011-10:OU-NTIVideo-CLC3403_LawAndJustice.ntivideo.video_01.01'
READING = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:04.01_RequiredReading'
SUB_SECTION = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.subsec:BOOK_5_CHAPTER_3'

class MockCatalog(object):
	def get_containers(self, _):
		course_ntiid = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice'
		return (course_ntiid,)

class TestPathLookup( ApplicationLayerTest ):
	layer = PersistentInstructedCourseApplicationTestLayer
	testapp = None
	default_origin = str('http://janux.ou.edu')

	@WithSharedApplicationMockDS(users=True,testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_catalog')
	@fudge.patch('nti.app.products.courseware.adapters.is_readable')
	def test_contained(self, mock_get_catalog, mock_readable ):
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns( mock_catalog )
		# Not sure why we need this.
		mock_readable.is_callable().returns( True )

		# Get reading
		path = '/dataserver2/LibraryPath?objectId=%s' % READING
		res = self.testapp.get( path )
		res = res.json_body

		# No LessonOverview registered, so we lose outline.
		# We do get course followed by appropriate page info.
		assert_that( res, has_length( 1 ))
		res = res[0]
		assert_that( res, has_length( 2 ))
		assert_that( res[0], has_entry( 'Class', 'CourseInstance' ))
		assert_that( res[1], has_entries( 'Class', 'PageInfo',
										'NTIID', READING,
										'Title', '4.1 Homicide Law of Draco' ))

		# Video
		path = '/dataserver2/LibraryPath?objectId=%s' % VIDEO
		res = self.testapp.get( path )
		res = res.json_body

		# No LessonOverview registered, so we lose outline.
		# We do get course followed by appropriate page info.
		assert_that( res, has_length( 1 ))
		res = res[0]
		assert_that( res, has_length( 3 ))
		assert_that( res[0], has_entry( 'Class', 'CourseInstance' ))
		assert_that( res[1], has_entries( 'Class', 'PageInfo',
										'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.lec:01_LESSON',
										'Title', '1. Defining Law and Justice'))
		assert_that( res[2], has_entries( 'Class', 'Video',
										'NTIID', VIDEO ))

		# Sub section
		path = '/dataserver2/LibraryPath?objectId=%s' % SUB_SECTION
		res = self.testapp.get( path )
		res = res.json_body

		# No LessonOverview registered, so we lose outline.
		# We do get course followed by appropriate page info.
		assert_that( res, has_length( 1 ))
		res = res[0]
		assert_that( res, has_length( 2 ))

		assert_that( res[0], has_entry( 'Class', 'CourseInstance' ))
		assert_that( res[1], has_entries( 'Class', 'PageInfo',
										# XXX Does this NTIID make sense?
										'NTIID', 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:01.01_RequiredReading',
										'Title', '1.1 Aristotle, Nicomachean Ethics, 5.3-5.8' ))

