#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import has_property
from hamcrest import has_length
from hamcrest import has_entry
from hamcrest import all_of
from hamcrest import has_entries

from nti.testing import base
from nti.testing import matchers
from nti.testing.matchers import verifiably_provides

import os.path

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS


from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection
from ..interfaces import ICoursesWorkspace
from nti.dataserver import users

from nti.dataserver.tests import mock_dataserver
from nti.dataserver import traversal

class TestWorkspace(SharedApplicationTestBase):

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		lib = Library(
					paths=(os.path.join(
									os.path.dirname(__file__),
									'Library',
									'IntroWater'),
						   os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice')
				   ))
		return lib

	@WithSharedApplicationMockDS
	def test_workspace_links_in_service(self):
		with mock_dataserver.mock_db_trans(self.ds):
			user = self._create_user( username=self.extra_environ_default_user )
			service = IUserService(user)

			workspaces = service.workspaces

			assert_that( workspaces, has_item( verifiably_provides( ICoursesWorkspace )))

			workspace = [x for x in workspaces if ICoursesWorkspace.providedBy(x)][0]

			course_path = '/dataserver2/users/sjohnson%40nextthought.COM/Courses'
			assert_that( traversal.resource_path( workspace ),
						 is_( course_path ) )

			assert_that( workspace.collections, contains( verifiably_provides( ICollection ),
														  verifiably_provides( ICollection )))

			assert_that( workspace.collections, has_items( has_property( 'name', 'AllCourses'),
														   has_property( 'name', 'EnrolledCourses' )) )

			assert_that( [traversal.resource_path(c) for c in workspace.collections],
						 has_items( course_path + '/AllCourses',
									course_path + '/EnrolledCourses' ))


	@WithSharedApplicationMockDS(users=True,testapp=True)
	def test_fetch_all_courses(self):
		res = self.testapp.get( '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses' )


		assert_that( res.json_body, has_entry( 'Items', has_length( 2 )) )

		assert_that( res.json_body['Items'],
					 has_items(
						 all_of( has_entries( 'Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13')),
						 all_of( has_entries( 'Duration', None,
											  'Title', 'Law and Justice' )) ) )
