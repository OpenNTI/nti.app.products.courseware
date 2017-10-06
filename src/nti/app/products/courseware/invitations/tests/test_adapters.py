#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.invitations.interfaces import ICourseInvitations

from nti.app.products.courseware.invitations.model import PersistentCourseInvitation

from nti.contenttypes.courses.courses import CourseInstance

from nti.app.products.courseware.tests import CourseLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestAdapters(CourseLayerTest):

    @WithMockDSTrans
    def test_course_invitations(self):
        course = CourseInstance()
        invitations = ICourseInvitations(course, None)
        assert_that(invitations, is_not(none()))
        
        assert_that(invitations, validly_provides(ICourseInvitations))
        assert_that(invitations, verifiably_provides(ICourseInvitations))
        model = PersistentCourseInvitation(Code=u"1234-5",
                                           Scope=u"Public",
                                           Description=u"Inviation to course",
                                           Course=u"tag:nextthought.com,2011-10:NTI-OID-0x12345",
                                           IsGeneric=False)
        invitations.add(model)
        assert_that(invitations, has_length(1))
        assert_that("1234-5", is_in(invitations))
        assert_that(list(invitations), has_length(1))
        assert_that(invitations.get_course_invitations(), 
                    has_length(1))
        
        invitations.remove(model)
        assert_that(invitations, has_length(0))
        
        model = PersistentCourseInvitation(Code=u"1234-5",
                                           Scope=u"Public",
                                           Description=u"Inviation to course",
                                           Course=u"tag:nextthought.com,2011-10:NTI-OID-0x12345",
                                           IsGeneric=False)
        invitations.add(model)
        invitations.clear()
        assert_that(invitations, has_length(0))

        
        