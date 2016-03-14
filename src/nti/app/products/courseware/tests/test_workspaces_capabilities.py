#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import assert_that
does_not = is_not

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestCapabilities(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = str('http://platform.ou.edu')

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_capabilities(self):
		instructor_env = self._make_extra_environ('harp4162')
		res = self.testapp.get('/dataserver2', extra_environ=instructor_env)
		caps = res.json_body.get('CapabilityList')
		assert_that(caps, does_not(has_item('nti.platform.courseware.advanced_editing')))

		res = self.testapp.get('/dataserver2')
		caps = res.json_body.get('CapabilityList')
		assert_that(caps, has_items('nti.platform.courseware.advanced_editing',
									'nti.platform.customization.can_change_password'))
