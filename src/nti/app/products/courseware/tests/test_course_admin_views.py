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
from hamcrest import not_none
from hamcrest import contains
from hamcrest import starts_with

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest
from . import LegacyInstructedCourseApplicationTestLayer
from . import InstructedCourseApplicationTestLayer

class _AbstractMixin(object):

	body_matcher = ()
	open_path = None

	comment_res = None

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_post_csv_create_forums(self):
		csv = b'CLC 3403,A clc discussion,Contents'
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, contains(*self.body_matcher) )

		inst_env = self._make_extra_environ(username='harp4162')
		inst_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )

		for i in self.body_matcher:
			if not isinstance(i, basestring):
				continue
			self.fetch_by_ntiid(i, extra_environ=inst_env)


		# And again does nothing
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		assert_that( res.json_body, is_([] ) )


		# If a student (who first enrolls)...
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		# ... makes a comment in one of those discussions...
		self.comment_res = self.testapp.post_json(self.open_path,
												  {'Class': 'Post', 'body': ['A comment']},
												  status=201)

		# ...it is not notable for the instructor
		res = self.fetch_user_recursive_notable_ugd(username='harp4162', extra_environ=inst_env )
		assert_that( res.json_body, has_entry( 'TotalItemCount', 0))

		self._extra_post_csv_create_forums()

	def _extra_post_csv_create_forums(self):
		pass



class TestCreateLegacyForums(_AbstractMixin,
							 ApplicationLayerTest):
	layer = LegacyInstructedCourseApplicationTestLayer
	testapp = None

	# This only works in the OU environment because that's where the purchasables are
	default_origin = str('http://janux.ou.edu')

	body_matcher = ['tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-Open_Discussions',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-Open_Discussions.A_clc_discussion',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Forum:GeneralCommunity-In_Class_Discussions',
					'tag:nextthought.com,2011-10:CLC3403.ou.nextthought.com-Topic:GeneralCommunity-In_Class_Discussions.A_clc_discussion']

	open_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/A_clc_discussion'


class TestCreateForums(_AbstractMixin,
					   ApplicationLayerTest):
	layer = InstructedCourseApplicationTestLayer
	testapp = None

	# This only works in the OU environment because that's where the purchasables are
	default_origin = str('http://janux.ou.edu')

	body_matcher = [not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourse-Open_Discussions.A_clc_discussion',
					not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourse-In_Class_Discussions.A_clc_discussion']


	open_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/Discussions/Open_Discussions/A_clc_discussion'

	def _extra_post_csv_create_forums(self):
		# We should have absolute NTIIDs for the containerid of posts in
		# new-style topics
		assert_that( self.comment_res.json_body['ContainerId'],
					 starts_with('tag:nextthought.com,2011-10:harp4162-OID-0x') )
