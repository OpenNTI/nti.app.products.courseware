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
	default_origin = str('http://janux.ou.edu')

	body_matcher = ()
	open_path = None

	comment_res = None

	scope = str('')

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_post_csv_create_forums(self):
		csv = b'CLC 3403,A clc discussion,Contents' + self.scope
		res = self.testapp.post('/dataserver2/@@LegacyCourseTopicCreator', upload_files=[('ignored', 'foo.csv', csv)])

		res_ntiids = __traceback_info__ = res.json_body
		assert_that( res.json_body, contains(*self.body_matcher) )

		inst_env = self._make_extra_environ(username='harp4162')

		for i in self.body_matcher:
			if not isinstance(i, basestring):
				continue
			self.fetch_by_ntiid(i, extra_environ=inst_env)

		found_one = False
		for i in res_ntiids:
			if i:
				res = self.fetch_by_ntiid(i, extra_environ=inst_env)
				if res.json_body['Class'] == 'CommunityForum':
					#  XXX: Fragile
					found_one = True
					assert_that( res.json_body, has_entry("SharingScopeName", not_none()))
		assert found_one, "Need to check at least one board for the scope"

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


		# The instructor can easily make a small edit to the topic

		res = self.testapp.get(self.open_path, extra_environ=inst_env)
		headline_url = self.require_link_href_with_rel( res.json_body['headline'], 'edit' )
		self.testapp.put_json( headline_url,
								{'title': 'A New Title'},
							   extra_environ=inst_env)

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

	open_forum_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/'
	open_topic_path = '/dataserver2/users/CLC3403.ou.nextthought.com/DiscussionBoard/Open_Discussions/A_clc_discussion'
	open_path = open_topic_path


class TestCreateLegacyForumsOpenOnly(TestCreateLegacyForums):

	layer = LegacyInstructedCourseApplicationTestLayer
	testapp = None

	body_matcher = TestCreateLegacyForums.body_matcher[:3] # All three, because the in-class discussions still created, but not the topic

	scope = str(',Open')

class TestCreateForums(_AbstractMixin,
					   ApplicationLayerTest):
	layer = InstructedCourseApplicationTestLayer
	testapp = None

	# This only works in the OU environment because that's where the purchasables are
	default_origin = str('http://janux.ou.edu')

	body_matcher = [not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-Open_Discussions.A_clc_discussion',
					not_none(),
					'tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-In_Class_Discussions.A_clc_discussion']



	open_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/Discussions/Open_Discussions/A_clc_discussion'
	default_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/Discussions/Forum'

	def _extra_post_csv_create_forums(self):
		# We should have absolute NTIIDs for the containerid of posts in
		# new-style topics
		assert_that( self.comment_res.json_body['ContainerId'],
					 starts_with('tag:nextthought.com,2011-10:unknown-OID-0x') )

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_create_topic_directly(self):
		inst_env = self._make_extra_environ(username='harp4162')

		topic_res = self.testapp.post_json(self.default_path,
										   { 'Class': 'Post',
											 'title': 'My New Blog',
											 'description': "This is a description of the thing I'm creating",
											 'body': ['My first thought'] },
										   status=201,
										   extra_environ=inst_env)
		assert_that( topic_res.json_body,
					 has_entry('NTIID',
							   starts_with('tag:nextthought.com,2011-10:unknown-OID-0x') ) )
		assert_that( topic_res.json_body,
					 has_entry('ContainerId',
							   starts_with('tag:nextthought.com,2011-10:unknown-OID-0x') ) )

class TestCreateForumsOpenOnly(TestCreateForums):

	layer = InstructedCourseApplicationTestLayer
	testapp = None

	body_matcher = TestCreateForums.body_matcher[:3] # All three, because the in-class discussions still created, but not the topic

	scope = str(',Open')

class TestMigrate(ApplicationLayerTest):

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_migrate_legacy_to_new(self):
		res = self.testapp.post('/dataserver2/@@SyncAllLibraries')
		res = self.testapp.get('/dataserver2/@@LegacyCourseEnrollmentMigrator')
		assert_that( res.json_body, is_(
			[['Nothing in site', 'demo.nextthought.com'],
			 ['Nothing in site', 'labs.symmys.com'],
			 ['Nothing in site', 'law.nextthought.com'],
			 ['Nothing in site', 'mathcounts.nextthought.com'],
			 ['Nothing in site', 'personalleadership.nextthought.com'],
			 ['Fall2014/BIOL 2124',
			  'No community',
			  {'public': 'BIOL2124F2014.ou.nextthought.com', 'restricted': None}],
			 ['Fall2014/CHEM 1315',
			  'No community',
			  {'public': 'CHEM1315F2014.ou.nextthought.com',
			   'restricted': 'CHEM1315Fall2014.ou.nextthought.com'}],
			 ['Fall2014/CHEM 4970/SubInstances/001',
			  'No community',
			  {'public': 'CHEM4970F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:morv1533-MeetingRoom:Group-chem4970fall2014.ou.nextthought.com'}],
			 ['Fall2014/CLC 3403',
			  'No community',
			  {'public': 'CLC3403F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:harp4162-MeetingRoom:Group-clc3403fall2014.ou.nextthought.com'}],
			 ['Fall2014/IAS 2003',
			  'No community',
			  {'public': 'IAS2003F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:gril4990-MeetingRoom:Group-ias2003fall2014.ou.nextthought.com'}],
			 ['Fall2014/PHIL 1203',
			  'No community',
			  {'public': 'PHIL1203F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:judi5807-MeetingRoom:Group-phil1203fall2014.ou.nextthought.com'}],
			 ['Fall2014/SOC 1113',
			  'No community',
			  {'public': 'SOC1113F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:damp8528-MeetingRoom:Group-soc1113fall2014.ou.nextthought.com'}],
			 ['Fall2014/UCOL 1002',
			  'No community',
			  {'public': 'UCOL1002F2014.ou.nextthought.com', 'restricted': None}],
			 ['Nothing in site', 'prmia.nextthought.com'],
			 ['Nothing in site', 'rwanda.nextthought.com'],
			 ['Nothing in site', 'symmys-alpha.nextthought.com'],
			 ['Nothing in site', 'symmys.nextthought.com'],
			 ['Nothing in site', 'testmathcounts.nextthought.com'],
			 ['Nothing in site', 'testprmia.nextthought.com']]
		))
