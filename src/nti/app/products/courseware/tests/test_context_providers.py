#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import has_length
from hamcrest import assert_that

from nti.appserver.context_providers import get_joinable_contexts
from nti.appserver.context_providers import get_top_level_contexts
from nti.appserver.context_providers import get_trusted_top_level_contexts

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.ntiids.ntiids import find_object_with_ntiid

class MockCatalog(object):
	def get_containers(self, _):
		course_ntiid = 'tag:nextthought.com,2011-10:OU-HTML-ENGR1510_Intro_to_Water.course_info'
		return (course_ntiid,)

class TestContextProviders(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	testapp = None
	default_origin = str('http://janux.ou.edu')

	@WithSharedApplicationMockDS(users=True, testapp=True)
	@fudge.patch('nti.app.products.courseware.adapters.get_library_catalog')
	@fudge.patch('nti.app.products.courseware.adapters.is_readable')
	@fudge.patch('nti.app.products.courseware.adapters._is_user_enrolled')
	def test_providers(self, mock_get_catalog, mock_readable, mock_enrolled):
		containerId = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.sec:04.01_RequiredReading"
		mock_catalog = MockCatalog()
		mock_get_catalog.is_callable().returns(mock_catalog)
		# Not sure why we need this.
		mock_readable.is_callable().returns(True)
		mock_enrolled.is_callable().returns(False)

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			obj = find_object_with_ntiid(containerId)
			results = get_joinable_contexts(obj)
			assert_that(results, has_length(3))

			mock_enrolled.is_callable().returns(True)
			results = get_top_level_contexts(obj)
			assert_that(results, has_length(3))

			results = get_trusted_top_level_contexts(obj)
			assert_that(results, has_length(3))
