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
from hamcrest import greater_than_or_equal_to

import csv
from io import BytesIO

from nti.app.testing.decorators import WithSharedApplicationMockDS

class AbstractMixin(object):

	default_username = 'normaluser'
	default_origin = str('http://janux.ou.edu')

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

	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',), testapp=True, default_authenticate=True)
	def test_post_csv_create_forums(self):
		self._do_test_post_csv_create_forums(self.contents)

	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',), testapp=True, default_authenticate=True)
	def test_post_csv_create_forums_alt_syntax(self):
		self._do_test_post_csv_create_forums(self.contents, video='[ntivideo][kaltura]kaltura://1500101/1_vkxo2g66/')

	@WithSharedApplicationMockDS(users=('sjohnson@nextthought.com',), testapp=True, default_authenticate=True)
	def test_post_csv_create_forums_mac(self):
		self._do_test_post_csv_create_forums(self.mac_contents, full=False)

	def _do_test_post_csv_create_forums(self, contents, full=True, video='[ntivideo]kaltura://1500101/1_vkxo2g66/'):
		inst_env = self._make_extra_environ(username='harp4162')
		admin_env = self._make_extra_environ(username='sjohnson@nextthought.com')

		sio = BytesIO()
		csv_writer = csv.writer(sio)
		enrolled_course_id = getattr(self, 'enrollment_ntiid', None) \
						or 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'

		header_row = ['NTIID', 'DiscussionTitle', 'Body 1', 'Body 2']
		row = [enrolled_course_id, 'A clc discussion', contents, video]
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
		assert_that(csv.DictReader(BytesIO(csv_str)).next()['Body 1'], is_(contents))

		res = self.testapp.post('/dataserver2/CourseAdmin/LegacyCourseTopicCreator',
								upload_files=[('ignored', 'foo.csv', csv_str)],
								extra_environ=admin_env)

		res_ntiids = __traceback_info__ = res.json_body
		assert_that(res.json_body, contains(*self.body_matcher))

		for i in self.body_matcher:
			if not isinstance(i, basestring):
				continue
			res = self.fetch_by_ntiid(i, extra_environ=inst_env)
			if 'Topic' in res.json_body['Class']:
				assert_that(res.json_body['headline']['body'][0],
							 # Yes, the one with the newlines, never \r
							 is_(self.contents.decode('windows-1252')))
				assert_that(res.json_body['headline']['body'][1],
							 has_entries('Class', 'EmbeddedVideo',
										 'type', 'kaltura',
										 'embedURL', 'kaltura://1500101/1_vkxo2g66/',
										 'href', starts_with('/dataserver2')))

		if not full:
			return

		found_topic = False
		found_forum = False
		for i in res_ntiids:
			if i:
				res = self.fetch_by_ntiid(i, extra_environ=inst_env)
				if res.json_body['Class'] == 'CommunityForum':
					# XXX: Fragile
					found_forum = True
					assert_that(res.json_body, has_entry("SharingScopeName", not_none()))
					# The instructor should have an 'add' href for the forum
					self.require_link_href_with_rel(res.json_body, 'add')

					board_res = self.fetch_by_ntiid(res.json_body['ContainerId'], extra_environ=inst_env)
					# The instructor should have an 'add' href for the board
					assert_that(board_res.json_body['Class'], contains_string('Board'))
					self.require_link_href_with_rel(board_res.json_body, 'add')

				else:
					found_topic = True
					# The instructor should have an 'add' href for the forum
					self.require_link_href_with_rel(res.json_body, 'add')

					assert_that(res.json_body['Class'], contains_string('Topic'))

		assert found_forum, "Need to check at least one forum for the scope"
		assert found_topic, "Need to check at least one topic for the scope"

		# And again does nothing
		res = self.testapp.post('/dataserver2/CourseAdmin/LegacyCourseTopicCreator',
								upload_files=[('ignored', 'foo.csv', csv_str)],
								extra_environ=admin_env)

		assert_that(res.json_body, is_([]))


		# If a student (who first enrolls)...
		res = self.post_user_data(enrolled_course_id,
								  extra_path='/Courses/EnrolledCourses',
								  status=201)
                res = res.json_body
                course_href = self.require_link_href_with_rel(res, 'CourseInstance')
                res = self.testapp.get(course_href)
		self._extra_student_checks(res, inst_env)

		# ... makes a comment in one of those discussions...
		self.comment_res = self.testapp.post_json(self.open_path,
												  {'Class': 'Post', 'body': ['A comment']},
												  status=201)

		# ...it is notable for the instructor (only legacy ACLCommunityForums)...
		res = self.fetch_user_recursive_notable_ugd(username='harp4162', extra_environ=inst_env)
		assert_that(res.json_body, has_entry('TotalItemCount', greater_than_or_equal_to(2)))
		#assert_that(res.json_body, has_entry('TotalItemCount', is_( 0 )))

		# ... the change is also in the instructors stream (why?)...
		res = self.fetch_user_root_rstream(username='harp4162', extra_environ=inst_env)
		assert_that(res.json_body['Items'],
					has_item(has_entries('Creator', self.default_username,
										  'Item', has_entries('Class', 'GeneralForumComment',
															  'body', ['A comment']))))

		# ...Likewise, the discussion change is in the stream for the instructor (why?),
		# and the discussion itself (only legacy ACLCommunityForums).
		for username, env in (('harp4162', inst_env),
							  # (self.default_username, None)
						  ):
			res = self.fetch_user_root_rstream(username=username, extra_environ=env)
			assert_that(res.json_body['Items'],
						has_item(has_entries('ChangeType', 'Shared',
											  'Item', has_entries('Class', 'CommunityHeadlineTopic',
																  'title', 'A clc discussion'))))

		# The admin can easily make a small edit to the topic...
		res = self.testapp.get(self.open_path, extra_environ=admin_env)

# 		headline_url = self.require_link_href_with_rel( res.json_body['headline'], 'edit' )
# 		self.testapp.put_json( headline_url,
# 								{'title': 'A New Title'},
# 							   extra_environ=admin_env)
#
# 		# ...though the student cannot
# 		self.testapp.put_json( headline_url, {'title': 'From the student'},
# 							   status=403 )
#
# 		# XXX: The instructor should or should not be able to make an edit? At the moment,
# 		# he cannot. (This way we could potentially use the creator to update)
# 		self.testapp.put_json( headline_url, {'title': 'From the inst'},
# 							   extra_environ=inst_env,
# 							   status=403 )

		self._extra_post_csv_create_forums()

	def _extra_post_csv_create_forums(self):
		pass

	def _extra_student_checks(self, res, inst_env):
		# everybody can be resolved by the student
		# XXX: This test doesn't exactly belong here, but it's convenient
		for o in res.json_body['SharingScopes']['Items'].values():

			self.resolve_user(username=o['NTIID'])
			self.resolve_user(username=o['Username'])
			self.resolve_user(username=o['OID'])

			self.resolve_user(username=o['NTIID'], extra_environ=inst_env)
			self.resolve_user(username=o['Username'], extra_environ=inst_env)
			self.resolve_user(username=o['OID'], extra_environ=inst_env)

_AbstractMixin = AbstractMixin
