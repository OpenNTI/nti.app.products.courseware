#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from StringIO import StringIO

from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler

from nti.app.products.courseware.resources.utils import is_internal_file_link

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

class TestCourseFiler(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	@classmethod
	def course_entry(cls):
		return find_object_with_ntiid(cls.entry_ntiid)

	@WithSharedApplicationMockDS(testapp=False, users=True)
	def test_filer(self):

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			course = ICourseInstance(self.course_entry())
			filer = ICourseSourceFiler(course, None)
			assert_that(filer, is_(not_none()))

			source = StringIO("<ichigo/>")
			href = filer.save("ichigo.xml", source, contentType="text/xml",
							  overwrite=True)
			assert_that(is_internal_file_link(href), is_(True))

			obj = filer.get(href)
			assert_that(filer, is_(not_none()))
			assert_that(obj, has_property('filename', 'ichigo.xml'))
			assert_that(obj, has_property('contentType', "text/xml"))

			source = StringIO("<ichigo/>")
			href = filer.save("ichigo.xml", source, contentType="text/xml",
							  overwrite=True, bucket="bleach/shikai")
			assert_that(is_internal_file_link(href), is_(True))

			obj = filer.get("/bleach/shikai/ichigo.xml")
			assert_that(filer, is_(not_none()))

			assert_that(filer.is_bucket("/bleach/shikai"), is_(True))
			assert_that(filer.list("/bleach/shikai"), is_((u'/bleach/shikai/ichigo.xml',)))

			assert_that(filer.remove(href), is_(True))
			assert_that(filer.list("/bleach/shikai"), is_(()))
