#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import not_
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

import anyjson as json

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

import nti.dataserver.tests.mock_dataserver as mock_dataserver


class TestCourseUGDViews(ApplicationLayerTest):
    """
    We expect to be able to post UGD to a 'Pages' link
    in the course and that the returned ugd will contain
    this course context.
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    container_ntiid = u"tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.subsec:BOOK_Three_PART_1"

    course_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice'

    user_pages_href = '/dataserver2/users/sjohnson@nextthought.com/Pages'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_ugd(self):
        course = self.testapp.get(self.course_href)
        course_json = course.json_body
        # For our law course, get the pages href and the course ntiid
        course_links = course_json.get('Links')
        for link in course_links:
            if link.get('rel') == 'Pages':
                pages_href = link.get('href')
        course_ntiid = course_json.get('NTIID')

        data = json.serialize({
            'Class': 'Highlight', 'MimeType': 'application/vnd.nextthought.highlight',
            'ContainerId': self.container_ntiid,
            'selectedText': "This is the selected text",
            'applicableRange': {'Class': 'ContentRangeDescription'}
        })

        self.testapp.post(pages_href, data, status=201)

        user_ugd_path = self.user_pages_href
        user_ugd_path += '(' + self.container_ntiid + ')/UserGeneratedData'
        user_ugd = self.testapp.get(user_ugd_path)
        user_ugd = user_ugd.json_body
        highlight_json = user_ugd.get('Items')[0]
        assert_that(highlight_json,
                    has_entry('ContainerContext', course_ntiid))

    @WithSharedApplicationMockDS(testapp=True, users=True, default_authenticate=True)
    def test_relevant_ugd(self):

        environ = self._make_extra_environ('sjohnson@nextthought.com')
        course = self.testapp.get(self.course_href)
        course_json = course.json_body

        # For our law course, get the pages href and the course ntiid
        course_links = course_json.get('Links')
        for link in course_links:
            if link.get('rel') == 'Pages':
                pages_href = link.get('href')
        course_ntiid = course_json.get('NTIID')

        # Add a highlight and associate its context_id with the container
        # context
        data = json.serialize({
            'Class': 'Highlight', 'MimeType': 'application/vnd.nextthought.highlight',
            'ContainerId': self.container_ntiid,
            'selectedText': "This is the selected text",
            'applicableRange': {'Class': 'ContentRangeDescription'}
        })

        response = self.testapp.post(pages_href, data,
                                     status=201, extra_environ=environ)
        highlight_ntiid = response.json_body['NTIID']

        with mock_dataserver.mock_db_trans(self.ds):
            highlight = find_object_with_ntiid(highlight_ntiid)
            # set context id
            highlight.context_id = response.json_body['ContainerContext']

        data = json.serialize({
            'Class': 'Highlight', 'MimeType': 'application/vnd.nextthought.highlight',
            'ContainerId': self.container_ntiid,
            'selectedText': "Different selected text",
            'applicableRange': {'Class': 'ContentRangeDescription'}
        })

        # Add another highlight, but this time set it to a fake container
        # context
        response = self.testapp.post(pages_href, data,
                                     status=201, extra_environ=environ)
        highlight_ntiid = response.json_body['NTIID']

        with mock_dataserver.mock_db_trans(self.ds):
            highlight = find_object_with_ntiid(highlight_ntiid)
            # set context id
            highlight.context_id = "not a container ID"

        # When we get UGD for this object, we should get back
        # the first highlight, but not the second
        course_ugd_path = self.course_href
        course_ugd_path += '/Pages(' + self.container_ntiid + ')/RelevantUGD'
        self.testapp.get(course_ugd_path, extra_environ=environ)
        course_ugd = self.testapp.get(course_ugd_path)
        course_ugd = course_ugd.json_body
        assert_that(course_ugd['Items'], has_length(1))
        highlight_json = course_ugd.get('Items')[0]
        assert_that(highlight_json,
                    has_entry('ContainerContext', course_ntiid))
        assert_that(highlight_json,
                    has_entry('selectedText', "This is the selected text"))
        assert_that(highlight_json,
                    not_(has_entry('selectedText', "Different selected text")))
