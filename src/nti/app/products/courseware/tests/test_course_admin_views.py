#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
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
from hamcrest import empty
from hamcrest import not_none
from hamcrest import greater_than

from zope import component

from nti.testing.matchers import verifiably_provides

import os.path
import datetime
import webob.datetime_utils

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.appserver.interfaces import IUserService
from nti.appserver.interfaces import ICollection

from nti.dataserver.tests import mock_dataserver
from nti.dataserver import traversal

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICourseCatalog

class TestCreateForums(SharedApplicationTestBase):
	testapp = None

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

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_post_csv_create_forums(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# Now that we have created the instructor user, we need to re-enumerate
		# the library so it gets noticed
		with mock_dataserver.mock_db_trans(self.ds):
			cat = component.getUtility(ICourseCatalog)
			del cat._entries[:]
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')


		csv = b'CLC 3403,A clc discussion,Contents'


		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, is_([u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-Open_Discussions',
										 u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-Open_Discussions.A_clc_discussion',
										 u'tag:nextthought.com,2011-10:harp4162-Forum:GeneralCommunity-In_Class_Discussions',
										 u'tag:nextthought.com,2011-10:harp4162-Topic:GeneralCommunity-In_Class_Discussions.A_clc_discussion'] ) )


		# And again does nothing
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, is_([] ) )
