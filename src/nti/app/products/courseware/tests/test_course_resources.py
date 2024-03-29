#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
does_not = is_not

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

ITEMS = StandardExternalFields.ITEMS


class TestCourseResoures(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @classmethod
    def catalog_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    def course_oid(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = self.catalog_entry()
            result = to_external_ntiid_oid(ICourseInstance(entry))
            return result

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_upload(self):
        course_ntiid = self.course_oid()
        href = '/dataserver2/Objects/%s/resources' % course_ntiid
        res = self.testapp.post(href + '/@@upload',
                                upload_files=[('ichigo.txt', 'ichigo.txt', b'ichigo'),
                                              ('aizen.txt', 'aizen.txt', b'aizen')],
                                status=201)
        assert_that(res.json_body,
                    has_entries('ItemCount', is_(2),
                                ITEMS, has_length(2)))
        items = res.json_body[ITEMS]
        assert_that(items[0],
                    has_entry('MimeType', 'application/vnd.nextthought.courseware.contentfile'))
        assert_that(items[1],
                    has_entry('MimeType', 'application/vnd.nextthought.courseware.contentfile'))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_mkdir(self):
        course_ntiid = self.course_oid()
        href = '/dataserver2/Objects/%s/resources' % course_ntiid

        self.testapp.post_json(href + '/@@mkdir', {})
        self.testapp.post_json(href + '/@@mkdir', {})

        data = {'name': 'CLC3403'}
        res = self.testapp.post_json(href + '/@@mkdir',
                                     data,
                                     status=201)
        assert_that(res.json_body,
                    has_entry('MimeType', 'application/vnd.nextthought.courseware.contentfolder'))

        data = {'path': 'bleach/ichigo/shikai'}
        res = self.testapp.post_json(href + '/@@mkdirs',
                                     data,
                                     status=201)
        assert_that(res.json_body,
                    has_entries('MimeType', 'application/vnd.nextthought.courseware.contentfolder',
                                'path', '/bleach/ichigo/shikai'))
