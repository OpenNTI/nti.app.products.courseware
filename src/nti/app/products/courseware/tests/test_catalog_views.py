#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"


from hamcrest import assert_that
from hamcrest import has_entry

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestCatalogViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	@WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=False)
	def test_anonymously_available_courses_view(self):
		anonymous_instances_url = '/dataserver2/_AnonymouslyButNotPubliclyAvailableCourseInstances'


		#Anonymous requests that aren't our special classifier prompt for auth
		unauthed_environ = self._make_extra_environ(username=None)
		self.testapp.get(anonymous_instances_url, extra_environ=unauthed_environ, status=401)

		#authed users also can't login
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user('ichigo')

		unauthed_environ = self._make_extra_environ(username='ichigo')
		self.testapp.get(anonymous_instances_url, extra_environ=unauthed_environ, status=403)

		#unauthed requests that have our special classifier are allowed
		extra_environ = self._make_extra_environ(username=None)
		extra_environ['nti.paste.testing.classification'] = 'application-tvos'
		result = self.testapp.get(anonymous_instances_url, extra_environ=extra_environ, status=200)
		result = result.json_body
		assert_that(result, has_entry('ItemCount', 1))
