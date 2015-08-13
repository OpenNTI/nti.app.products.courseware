#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_item
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import starts_with
from hamcrest import contains_string

import csv
import fudge
from io import BytesIO

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer
from nti.app.products.courseware.tests import LegacyInstructedCourseApplicationTestLayer

class _AbstractMixin(object):
	default_origin = str('http://janux.ou.edu')
	default_username = 'normaluser'

	body_matcher = ()
	open_path = None

	comment_res = None

	scope = str('')

	contents = """
	This is the contents.
	Of the headline post

	Notice --- it has leading and trailing spaces, and even
	commas and blank lines. You can\u2019t ignore the special apostrophe.""".encode('windows-1252')

	mac_contents = contents.replace(b'\n', b'\r')

	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',),testapp=True,default_authenticate=True)
	def test_post_csv_create_forums(self):
		self._do_test_post_csv_create_forums(self.contents)

	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',),testapp=True,default_authenticate=True)
	def test_post_csv_create_forums_alt_syntax(self):
		self._do_test_post_csv_create_forums(self.contents, video='[ntivideo][kaltura]kaltura://1500101/1_vkxo2g66/')


	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',),testapp=True,default_authenticate=True)
	def test_post_csv_create_forums_mac(self):
		self._do_test_post_csv_create_forums(self.mac_contents,full=False)

	def _do_test_post_csv_create_forums(self, contents, full=True, video='[ntivideo]kaltura://1500101/1_vkxo2g66/'):
		inst_env = self._make_extra_environ(username='harp4162')
		admin_env = self._make_extra_environ(username='sjohnson@nextthought.com')

		sio = BytesIO()
		csv_writer = csv.writer(sio)
		header_row = ['NTIID', 'DiscussionTitle', 'Body 1', 'Body 2']
		row = ['CLC 3403', 'A clc discussion', contents, video]
		if self.scope:
			header_row.append('DiscussionScope')
			row.append(self.scope)
		csv_writer.writerow(header_row)
		csv_writer.writerow(row)
		# a duplicate winds up completely ignored because everything was already
		# created
		csv_writer.writerow(row)
		# so does a blank
		csv_writer.writerow([''])

		csv_str = sio.getvalue()
		assert_that( csv.DictReader(BytesIO(csv_str)).next()['Body 1'], is_(contents) )

		res = self.testapp.post('/dataserver2/CourseAdmin/LegacyCourseTopicCreator',
								upload_files=[('ignored', 'foo.csv', csv_str)],
								extra_environ=admin_env)

		res_ntiids = __traceback_info__ = res.json_body
		assert_that( res.json_body, contains(*self.body_matcher) )



		for i in self.body_matcher:
			if not isinstance(i, basestring):
				continue
			res = self.fetch_by_ntiid(i, extra_environ=inst_env)
			if 'Topic' in res.json_body['Class']:
				assert_that( res.json_body['headline']['body'][0],
							 # Yes, the one with the newlines, never \r
							 is_(self.contents.decode('windows-1252')) )
				assert_that( res.json_body['headline']['body'][1],
							 has_entries('Class', 'EmbeddedVideo',
										 'type', 'kaltura',
										 'embedURL', 'kaltura://1500101/1_vkxo2g66/',
										 'href', starts_with('/dataserver2')) )

		if not full:
			return

		found_topic = False
		found_forum = False
		for i in res_ntiids:
			if i:
				res = self.fetch_by_ntiid(i, extra_environ=inst_env)
				if res.json_body['Class'] == 'CommunityForum':
					#  XXX: Fragile
					found_forum = True
					assert_that( res.json_body, has_entry("SharingScopeName", not_none()))
					# The instructor should have an 'add' href for the forum
					self.require_link_href_with_rel(res.json_body, 'add')

					board_res = self.fetch_by_ntiid(res.json_body['ContainerId'], extra_environ=inst_env)
					# The instructor should have an 'add' href for the board
					assert_that( board_res.json_body['Class'], contains_string('Board'))
					self.require_link_href_with_rel(board_res.json_body, 'add')

				else:
					found_topic = True
					# The instructor should have an 'add' href for the forum
					self.require_link_href_with_rel(res.json_body, 'add')

					assert_that( res.json_body['Class'], contains_string('Topic'))


		assert found_forum, "Need to check at least one forum for the scope"
		assert found_topic, "Need to check at least one topic for the scope"

		# And again does nothing
		res = self.testapp.post('/dataserver2/CourseAdmin/LegacyCourseTopicCreator',
								upload_files=[('ignored', 'foo.csv', csv_str)],
								extra_environ=admin_env)

		assert_that( res.json_body, is_([] ) )


		# If a student (who first enrolls)...
		res = self.post_user_data('CLC 3403',
								  extra_path='/Courses/EnrolledCourses',
								  status=201 )
		self._extra_student_checks(res, inst_env)

		# ... makes a comment in one of those discussions...
		self.comment_res = self.testapp.post_json(self.open_path,
												  {'Class': 'Post', 'body': ['A comment']},
												  status=201)

		# ...it /is/ notable for the instructor...
		# (we previously tried to not make that so, but it only worked
		# for the first instructor, it was notable to everyone else because they were
		# explicitly listed in the ACL, which turns into direct-sharing)
		res = self.fetch_user_recursive_notable_ugd(username='harp4162', extra_environ=inst_env )
		assert_that( res.json_body, has_entry( 'TotalItemCount', 2))

		# ... it is also in the instructors stream (why?)...
		res = self.fetch_user_root_rstream( username='harp4162', extra_environ=inst_env)
		assert_that( res.json_body['Items'],
					 has_item( has_entries('Creator', self.default_username,
										   'Item', has_entries('Class', 'GeneralForumComment',
															   'body', ['A comment']))) )

		# ...Likewise, the discussions are in the stream for the instructor...
		for username, env in (('harp4162', inst_env),
							  #(self.default_username, None)
						  ):
			res = self.fetch_user_root_rstream( username=username, extra_environ=env )
			assert_that( res.json_body['Items'],
						 has_item( has_entries('ChangeType', 'Shared',
											   'Item', has_entries('Class', 'CommunityHeadlineTopic',
																   'title', 'A clc discussion'))) )

		# The admin can easily make a small edit to the topic...
		res = self.testapp.get(self.open_path, extra_environ=admin_env)
		headline_url = self.require_link_href_with_rel( res.json_body['headline'], 'edit' )
		self.testapp.put_json( headline_url,
								{'title': 'A New Title'},
							   extra_environ=admin_env)

		# ...though the student cannot
		self.testapp.put_json( headline_url, {'title': 'From the student'},
							   status=403 )

		# XXX: The instructor should or should not be able to make an edit? At the moment,
		# he cannot. (This way we could potentially use the creator to update)
		self.testapp.put_json( headline_url, {'title': 'From the inst'},
							   extra_environ=inst_env,
							   status=403 )

		self._extra_post_csv_create_forums()

	def _extra_post_csv_create_forums(self):
		pass

	def _extra_student_checks(self, res, inst_env):
		# everybody can be resolved by the student
		# XXX: This test doesn't exactly belong here, but it's convenient
		for o in res.json_body['CourseInstance']['SharingScopes']['Items'].values():

			self.resolve_user(username=o['NTIID'])
			self.resolve_user(username=o['Username'])
			self.resolve_user(username=o['OID'])


			self.resolve_user(username=o['NTIID'], extra_environ=inst_env)
			self.resolve_user(username=o['Username'], extra_environ=inst_env)
			self.resolve_user(username=o['OID'], extra_environ=inst_env)

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
	scope = str('Open')

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
	@fudge.patch('nti.contenttypes.courses.catalog.CourseCatalogEntry.isCourseCurrentlyActive')
	def test_create_topic_directly(self, fake_active):
		# make it look like the course is in session
		fake_active.is_callable().returns(True)

		inst_env = self._make_extra_environ(username='harp4162')

		topic_res = self.testapp.post_json(self.default_path,
										   { 'Class': 'Post',
											 'title': 'My New Blog',
											 'description': "This is a description of the thing I'm creating",
											 'body': ['My first thought'] },
										   status=201,
										   extra_environ=inst_env)
		assert_that( topic_res.json_body,
					 # notability depends on mimetype
					 has_entry('MimeType', "application/vnd.nextthought.forums.communityheadlinetopic"))
		assert_that( topic_res.json_body,
					 has_entry('NTIID',
							   starts_with('tag:nextthought.com,2011-10:unknown-OID-0x') ) )
		assert_that( topic_res.json_body,
					 has_entry('ContainerId',
							   starts_with('tag:nextthought.com,2011-10:unknown-OID-0x') ) )

		# It is notable to a student...
		self.post_user_data('CLC 3403',
							extra_path='/Courses/EnrolledCourses',
							status=201 )
		res = self.fetch_user_recursive_notable_ugd()
		assert_that( res.json_body, has_entry( 'TotalItemCount', 0))

		# ... but only once its published
		self.testapp.post(self.require_link_href_with_rel(topic_res.json_body, 'publish'),
						  extra_environ=inst_env)
		res = self.fetch_user_recursive_notable_ugd()
		assert_that( res.json_body, has_entry( 'TotalItemCount', 1))

class TestCreateForumsOpenOnly(TestCreateForums):

	layer = InstructedCourseApplicationTestLayer
	testapp = None

	body_matcher = TestCreateForums.body_matcher[:3] # All three, because the in-class discussions still created, but not the topic

	scope = str('Open')

class TestMigrate(ApplicationLayerTest):

	@WithSharedApplicationMockDS(users=True,testapp=True,default_authenticate=True)
	def test_migrate_legacy_to_new(self):
		self.testapp.post('/dataserver2/@@SyncAllLibraries')
		res = self.testapp.get('/dataserver2/CourseAdmin/LegacyCourseEnrollmentMigrator')
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
			 ['Fall2014/CHEM 4970/SubInstances/100',
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
