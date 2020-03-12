#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import has_items
from hamcrest import has_entries
from hamcrest import has_properties

from zope import interface

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance

from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestTabPreference(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    @WithMockDSTrans
    def test_section_course_tab_preferences(self):
        parent_course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(parent_course)

        child_course = ContentCourseSubInstance()
        parent_course.SubInstances['child1'] = child_course

        child_course2 = ContentCourseSubInstance()
        parent_course.SubInstances['child2'] = child_course2
        child_course2.prepare_own_outline()

        parent_prefs = ICourseTabPreferences(parent_course)
        child_prefs= ICourseTabPreferences(child_course)
        child_prefs2 = ICourseTabPreferences(child_course2)

        assert_that(parent_prefs, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))
        assert_that(child_prefs, has_properties({'names': has_length(0),
                                                 'order': has_length(0)}))
        assert_that(child_prefs2, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))

        parent_prefs.update_names({'A': 1, 'B': 2})
        parent_prefs.update_order(['A', 'B'])
        assert_that(parent_prefs, has_properties({'names': has_entries({'A': 1, 'B': 2}),
                                                  'order': contains('A', 'B')}))
        assert_that(child_prefs, has_properties({'names': has_length(2),
                                                 'order': contains('A', 'B')}))
        assert_that(child_prefs2, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))

        child_prefs.update_names({'C': 3, 'A': 5})
        child_prefs.update_order(['C', 'A'])
        assert_that(parent_prefs, has_properties({'names': has_entries({'A': 1, 'B': 2}),
                                                  'order': contains('A', 'B')}))
        assert_that(child_prefs, has_properties({'names': has_entries({'A': 5, 'B': 2, 'C': 3}),
                                                 'order': contains('C', 'A')}))
        assert_that(child_prefs2, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))

        connection.add(parent_prefs._order)
        connection.add(parent_prefs._names)
        parent_prefs.clear()
        assert_that(parent_prefs, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))
        assert_that(child_prefs, has_properties({'names': has_entries({'A': 5, 'C': 3}),
                                                 'order': contains('C', 'A')}))
        assert_that(child_prefs2, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))

        child_prefs2.update_names({'e': 5})
        child_prefs2.update_order(['e'])
        assert_that(parent_prefs, has_properties({'names': has_length(0),
                                                  'order': has_length(0)}))
        assert_that(child_prefs, has_properties({'names': has_length(2),
                                                 'order': has_length(2)}))
        assert_that(child_prefs2, has_properties({'names': has_length(1),
                                                  'order': has_length(1)}))
