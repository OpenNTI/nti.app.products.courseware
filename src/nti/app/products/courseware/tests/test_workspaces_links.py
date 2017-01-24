#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from nti.testing.matchers import verifiably_provides

from urllib import unquote

from nti.app.products.courseware.interfaces import ICoursesWorkspace

from nti.appserver.workspaces.interfaces import ICollection
from nti.appserver.workspaces.interfaces import IUserService

from nti.traversal import traversal

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

class TestWorkspaceLinks(ApplicationLayerTest):

	testapp = None

	@WithSharedApplicationMockDS
	def test_workspace_links_in_service(self):
		with mock_dataserver.mock_db_trans(self.ds):
			user = self._create_user(username=self.extra_environ_default_user)
			service = IUserService(user)

			workspaces = service.workspaces

			assert_that(workspaces, has_item(verifiably_provides(ICoursesWorkspace)))

			workspace = [x for x in workspaces if ICoursesWorkspace.providedBy(x)][0]

			course_path = '/dataserver2/users/sjohnson%40nextthought.COM/Courses'
			assert_that(traversal.resource_path(workspace),
						 is_(unquote(course_path)))

			assert_that(workspace.collections, contains(verifiably_provides(ICollection),
														verifiably_provides(ICollection),
														verifiably_provides(ICollection)))

			assert_that(workspace.collections, has_items(has_property('name', 'AllCourses'),
														 has_property('name', 'EnrolledCourses'),
														 has_property('name', 'AdministeredCourses')))

			assert_that([traversal.resource_path(c) for c in workspace.collections],
						 has_items(course_path + '/AllCourses',
								   course_path + '/EnrolledCourses' ,
								   course_path + '/AdministeredCourses'))
