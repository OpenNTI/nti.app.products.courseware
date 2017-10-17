#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import contains_string
from hamcrest import contains_inanyorder
does_not = is_not

import os
import fudge
import simplejson

from zope import component

from nti.app.products.courseware.discussions import get_acl
from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import _extract_content
from nti.app.products.courseware.discussions import discussions_forums
from nti.app.products.courseware.discussions import create_course_forums
from nti.app.products.courseware.discussions import announcements_forums
from nti.app.products.courseware.discussions import get_forums_for_discussion
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.base._compat import text_

from nti.contentfragments.interfaces import SanitizedHTMLContentFragment

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.model import CourseDiscussion

from nti.dataserver.contenttypes.forums.forum import CommunityForum

from nti.dataserver.contenttypes.media import EmbeddedVideo

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.oids import to_external_ntiid_oid


class TestDiscussions(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    contents = u"""
	This is the contents of the headline post

	Notice --- it has leading and trailing spaces, and even
	commas and blank lines. You can\u2019t ignore the special apostrophe.
	"""

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    vendor_info = {
        "NTI": {
            "Forums": {
                "AutoCreate": True,
                "HasInClassDiscussions": True,
                "HasOpenDiscussions": True
            },
        }
    }

    @classmethod
    def catalog_entry(self):
        catalog = component.getUtility(ICourseCatalog)
        for entry in catalog.iterCatalogEntries():
            if entry.ntiid == self.course_ntiid:
                return entry

    def test_extract_content_simple(self):
        content = _extract_content(
            (self.contents, u'[ntivideo][kaltura]kaltura://1500101/1_vkxo2g66/'))
        assert_that(content, is_(not_none()))
        assert_that(content, has_length(2))
        assert_that(content[0], has_length(169))
        assert_that(content[1], is_(EmbeddedVideo))

    def new_discussion(self):
        discussion = CourseDiscussion()
        content = _extract_content((self.contents,))[0]
        discussion.body = (SanitizedHTMLContentFragment(content),)
        discussion.scopes = (ES_ALL,)
        discussion.title = u'title'
        discussion.id = u"%s://%s" % (NTI_COURSE_BUNDLE, 'foo')
        return discussion

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.products.courseware.discussions.get_vendor_info')
    def test_discussion_creation(self, mock_gvi):

        mock_gvi.is_callable().with_args().returns(self.vendor_info)
        course_editor = u'janux_courses'
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(course_editor)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            discussions = ICourseDiscussions(course)
            discussion = discussions[u'foo'] = self.new_discussion()

            assert_that(discussions_forums(course), has_length(2))
            assert_that(announcements_forums(course), has_length(0))

            acl = get_acl(course)
            assert_that(acl, has_length(5))
            acls = []
            for ace in acl:
                try:
                    acls.append(ace.to_external_string())
                except AttributeError:
                    pass
            assert_that(acls, has_items('Allow:role:nti.admin:All',
                                        'Allow:harp4162:All',
                                        "Allow:janux_courses:['zope.View']"))

            result = create_course_forums(course)
            assert_that(result, has_entry('discussions',
                                          has_entries('ForCredit',
                                                      contains_inanyorder('In_Class_Discussions',
                                                                          is_(CommunityForum)),
                                                      'Public',
                                                      contains_inanyorder('Open_Discussions',
                                                                          is_(CommunityForum)))))

            discussions = result['discussions']
            discussion_hrefs = [x[1].NTIID for x in discussions.values()]
            for t in discussions.values():
                _, forum = t
                assert_that(forum, has_property('__acl__', has_length(6)))
                assert_that(forum, has_property('__entities__', has_length(1)))

            result = create_topics(discussion)
            assert_that(result,
                        has_item('tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-In_Class_Discussions._foo'))
            assert_that(result,
                        has_item('tag:nextthought.com,2011-10:CLC_3403-Topic:EnrolledCourseSection-Open_Discussions._foo'))

            assert_that(forum, has_key('_foo'))

            f4ds = get_forums_for_discussion(discussion, course)
            assert_that(f4ds, has_length(2))

        # Validate access
        for editor in (course_editor, 'harp4162'):
            editor_environ = self._make_extra_environ(editor)
            for href in discussion_hrefs:
                self.fetch_by_ntiid(href, extra_environ=editor_environ)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_discussion_get(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            discussions = ICourseDiscussions(course)
            discussions['foo'] = self.new_discussion()
            course_ntiid = to_external_ntiid_oid(course)

        url = '/dataserver2/Objects/%s/CourseDiscussions' % course_ntiid
        res = self.testapp.get(url, status=200)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courses.discussions',
                                'Items', has_length((1)),
                                'ItemCount', 1))

        url = '/dataserver2/Objects/%s/CourseDiscussions/foo' % course_ntiid
        res = self.testapp.get(url, status=200)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courses.discussion',
                                'ID', 'nti-course-bundle://foo'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_discussion_post(self):

        path = os.path.join(os.path.dirname(__file__), 'discussion.json')
        with open(path, "r") as fp:
            source = simplejson.loads(text_(fp.read()))

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            course_ntiid = to_external_ntiid_oid(course)

        url = '/dataserver2/Objects/%s/CourseDiscussions' % course_ntiid
        res = self.testapp.post_json(url, source, status=201)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courses.discussion',
                                'ID', contains_string('nti-course-bundle://Discussions/')))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_discussion_delete(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            discussions = ICourseDiscussions(course)
            discussions['foo'] = self.new_discussion()
            course_ntiid = to_external_ntiid_oid(course)

        url = '/dataserver2/Objects/%s/CourseDiscussions/foo' % course_ntiid
        self.testapp.delete(url, status=204)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            course = ICourseInstance(entry)
            discussions = ICourseDiscussions(course)
            assert_that(discussions, has_length(0))
