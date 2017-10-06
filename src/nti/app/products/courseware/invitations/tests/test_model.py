#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.app.products.courseware.invitations.model import CourseInvitation

from nti.app.products.courseware.tests import CourseLayerTest

from nti.externalization.tests import externalizes


class TestModel(CourseLayerTest):

    def test_model(self):
        model = CourseInvitation(Code=u"1234-5",
                                 Scope=u"Public",
                                 Description=u"Inviation to course",
                                 Course=u"tag:nextthought.com,2011-10:NTI-OID-0x12345",
                                 IsGeneric=False)

        assert_that(model, validly_provides(ICourseInvitation))
        assert_that(model, verifiably_provides(ICourseInvitation))

        assert_that(model, has_property('isGeneric', is_(False)))
        assert_that(model, has_property('IsGeneric', is_(False)))

        assert_that(model,
                    externalizes(has_entries('Class', 'CourseInvitation',
                                             'Code', '1234-5',
                                             'Scope', 'Public',
                                             'Description', 'Inviation to course',
                                             'MimeType', 'application/vnd.nextthought.invitations.courseinvitation')))
