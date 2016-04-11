#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCourseExporter(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

	@classmethod
	def catalog_entry(cls):
		return find_object_with_ntiid(cls.entry_ntiid)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_get_exporter(self):
		sections = tuple(x for x, _ in sorted(component.getUtilitiesFor(ICourseSectionExporter)))
		assert_that(sections, has_length(11))
		assert_that(sections, is_(
					(u'001:Bundle_Metainfo', 
					 u'002:Bundle_DC_Metadata',
					 u'003:Presentation_Assets',
					 u'004:Course_Info', 
					 u'005:Vendor_Info', 
					 u'006:Role_Info', 
					 u'008:Course_Outline', 
					 u'010:Assessments',
					 u'015:Lesson_Overviews', 
					 u'020:Course_Discussions',
					 u'100:Assignment_Policies')))
