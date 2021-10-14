#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from unittest import TestCase

from hamcrest import all_of
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import not_none

from nti.app.products.courseware.segments.interfaces import ENROLLED_IN
from nti.app.products.courseware.segments.interfaces import ICourseMembershipFilterSet
from nti.app.products.courseware.segments.interfaces import NOT_ENROLLED_IN

from nti.app.products.courseware.segments.tests import SharedConfiguringTestLayer

from nti.app.products.courseware.segments.model import CourseMembershipFilterSet

from nti.externalization import update_from_external_object

from nti.externalization.internalization import find_factory_for

from nti.externalization.tests import externalizes

from nti.testing.matchers import verifiably_provides


class TestCourseMembershipFilterSet(TestCase):

    layer = SharedConfiguringTestLayer

    def test_valid_interface(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        assert_that(CourseMembershipFilterSet(course_ntiid=course_ntiid,
                                              operator=ENROLLED_IN),
                    verifiably_provides(ICourseMembershipFilterSet))

    def _internalize(self, external):
        factory = find_factory_for(external)
        assert_that(factory, is_(not_none()))
        new_io = factory()
        if new_io is not None:
            update_from_external_object(new_io, external)
        return new_io

    def test_internalize(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        ext_obj = {
            "MimeType": CourseMembershipFilterSet.mime_type,
            "course_ntiid": course_ntiid,
            "operator": NOT_ENROLLED_IN
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, has_properties(
            course_ntiid=course_ntiid,
            operator=NOT_ENROLLED_IN
        ))

    def test_externalize(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        filter_set = CourseMembershipFilterSet(course_ntiid=course_ntiid,
                                               operator=ENROLLED_IN)
        assert_that(filter_set,
                    externalizes(all_of(has_entries({
                        'MimeType': CourseMembershipFilterSet.mime_type,
                        "course_ntiid": course_ntiid,
                        "operator": ENROLLED_IN,
                    }))))
