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

import os
import fudge

from zope import component

from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCourseImporter(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

	@classmethod
	def catalog_entry(cls):
		return find_object_with_ntiid(cls.entry_ntiid)

	@WithSharedApplicationMockDS(testapp=False, users=False)
	def test_get_importers(self):
		sections = tuple(x for x, _ in sorted(component.getUtilitiesFor(ICourseSectionImporter)))
		assert_that(sections, has_length(10))
		assert_that(sections, is_(
					(u'001:Bundle_Metainfo',
					 u'003:Presentation_Assets',
					 u'004:Course_Info',
					 u'008:Course_Outline', 
					 u'010:Assessments',
					 u'012:Evaluations',
					 u'015:Lesson_Overviews', 
					 u'100:Assignment_Policies',
					 u'666:Role_Info',
					 u'777:Vendor_Info',
					 u'888:Course_Discussions')))
		
	@WithSharedApplicationMockDS(testapp=True, users=True)
	@fudge.patch('nti.app.products.courseware.views.course_import_views.create_course',
				 'nti.app.products.courseware.views.course_import_views.import_course')
	def test_fake_imports(self, mock_create, mock_import):
		mock_create.is_callable().with_args().returns(False)
		mock_import.is_callable().with_args().returns(False)
		
		path = os.getcwd()
		href = '/dataserver2/CourseAdmin/@@ImportCourse'
		data = {'ntiid':self.entry_ntiid, 'path':path}
		self.testapp.post_json(href, data, status=200)

		data = {'admin':'Fall2015', 'key':'Bleach', 'path':path}
		self.testapp.post_json(href, data, status=200)
