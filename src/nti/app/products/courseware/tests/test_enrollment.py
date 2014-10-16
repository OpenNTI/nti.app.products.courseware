#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.app.products.courseware.utils import get_enrollment_options

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestEnrollmentOptions(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
	
	def catalog_entry(self):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid == self.course_ntiid:
				return entry
			
	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_get_enrollment_options(self):
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = self.catalog_entry()
			options = get_enrollment_options(entry)
			assert_that(options, is_not(none()))
			assert_that(options, has_entry('OpenEnrollment',
										   has_property('Enabled', is_(True))))
