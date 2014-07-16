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
from hamcrest import has_entry

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest
from . import LegacyInstructedCourseApplicationTestLayer


class TestCreateForums(ApplicationLayerTest):
	layer = LegacyInstructedCourseApplicationTestLayer
	testapp = None


	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_post_csv_create_forums(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		csv = b'CLC 3403,A clc discussion,Contents'
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, is_([u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-Open_Discussions',
										 u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-Open_Discussions.A_clc_discussion',
										 u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-In_Class_Discussions',
										 u'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-In_Class_Discussions.A_clc_discussion'] ) )

		inst_env = self._make_extra_environ(username='harp4162')
		inst_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		for i in res.json_body:
			self.fetch_by_ntiid(i, extra_environ=inst_env)

		# And again does nothing
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, is_([] ) )


		# If a student (who first enrolls)...
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		# ... makes a comment in one of those discussions...
		self.testapp.post_json('/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/A_clc_discussion',
							   {'Class': 'Post', 'body': ['A comment']},
							   status=201)
		# ...it is not notable for the instructor
		res = self.fetch_user_recursive_notable_ugd(username='harp4162', extra_environ=inst_env )
		assert_that( res.json_body, has_entry( 'TotalItemCount', 0))
