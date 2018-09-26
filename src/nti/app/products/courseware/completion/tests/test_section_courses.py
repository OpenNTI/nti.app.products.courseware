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
from hamcrest import has_length
from hamcrest import has_items

does_not = is_not

from zope import interface

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy

from nti.contenttypes.completion.tests.interfaces import ITestCompletableItem

from nti.contenttypes.completion.tests.test_models import MockCompletableItem

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.wref.interfaces import IWeakRef


@interface.implementer(IWeakRef)
class _IdentityWref(object):

    def __init__(self, gbe):
        self.gbe = gbe

    def __call__(self):
        return self.gbe

    def __eq__(self, unused_other):
        return True

    def __hash__(self):
        return 42


@interface.implementer(ITestCompletableItem)
class MockCompletableItem(PersistentCreatedAndModifiedTimeObject):

    def __init__(self, ntiid):
        self.ntiid = ntiid

    def __conform__(self, iface):
        if iface == IWeakRef:
            return _IdentityWref(self)


class TestSectionCourseCompletion(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    @WithMockDSTrans
    def test_section_completion(self):
        """
        Validate that child section course required state overrides that of
        the parent. We currently *cannot* make an item defined as required/
        optional in the parent revert to a default state.
        """
        parent_course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(parent_course)
        child_course = ContentCourseSubInstance()
        parent_course.SubInstances['child1'] = child_course
        parent_container = ICompletableItemContainer(parent_course)
        child_container = ICompletableItemContainer(child_course)
        default_1 = MockCompletableItem('default_1')
        parent_required_1 = MockCompletableItem('parent_required_1')
        parent_optional_1 = MockCompletableItem('parent_optional_1')
        child_required_1 = MockCompletableItem('child_required_1')
        child_optional_1 = MockCompletableItem('child_optional_1')
        parent_container.add_required_item(parent_required_1)
        parent_container.add_optional_item(parent_optional_1)
        child_container.add_required_item(child_required_1)
        child_container.add_optional_item(child_optional_1)

        assert_that(child_container.get_required_item_count(), is_(2))
        assert_that(child_container.get_optional_item_count(), is_(2))
        assert_that(child_container.is_item_required(parent_required_1),
                    is_(True))
        assert_that(child_container.is_item_required(parent_optional_1),
                    is_(False))
        assert_that(child_container.is_item_required(child_required_1),
                    is_(True))
        assert_that(child_container.is_item_required(child_optional_1),
                    is_(False))
        assert_that(child_container.is_item_required(default_1),
                    is_(False))

        assert_that(child_container.is_item_optional(parent_required_1),
                    is_(False))
        assert_that(child_container.is_item_optional(parent_optional_1),
                    is_(True))
        assert_that(child_container.is_item_optional(child_required_1),
                    is_(False))
        assert_that(child_container.is_item_optional(child_optional_1),
                    is_(True))
        assert_that(child_container.is_item_optional(default_1),
                    is_(False))

        # Can remove optional item from child
        child_container.remove_optional_item(child_optional_1)
        assert_that(child_container.is_item_optional(child_optional_1),
                    is_(False))

        # Cannot remove optional item from parent
        child_container.remove_optional_item(parent_optional_1)
        assert_that(child_container.is_item_optional(parent_optional_1),
                    is_(True))

        # Can remove required item from child
        child_container.remove_required_item(child_required_1)
        assert_that(child_container.is_item_required(child_required_1),
                    is_(False))

        # Cannot remove required item from parent
        child_container.remove_optional_item(parent_required_1)
        assert_that(child_container.is_item_required(parent_required_1),
                    is_(True))
        assert_that(child_container.get_required_item_count(), is_(1))
        assert_that(child_container.get_optional_item_count(), is_(1))

        # Mark parent required item as optional and parent optional item as
        # required; overrides parent
        child_container.add_optional_item(parent_required_1)
        assert_that(child_container.is_item_required(parent_required_1),
                    is_(False))
        assert_that(child_container.is_item_optional(parent_required_1),
                    is_(True))

        child_container.add_required_item(parent_optional_1)
        assert_that(child_container.is_item_required(parent_optional_1),
                    is_(True))
        assert_that(child_container.is_item_optional(parent_optional_1),
                    is_(False))
        assert_that(child_container.get_required_item_count(), is_(2))
        assert_that(child_container.get_optional_item_count(), is_(2))

    @WithMockDSTrans
    def test_section_default_required_policy(self):
        """
        Validate that child section course default required state inherits that of
        the parent.
        """
        parent_course = ContentCourseInstance()
        connection = mock_dataserver.current_transaction
        connection.add(parent_course)

        child_course = ContentCourseSubInstance()
        parent_course.SubInstances['child1'] = child_course

        child_course2 = ContentCourseSubInstance()
        parent_course.SubInstances['child2'] = child_course2
        child_course2.prepare_own_outline()

        parent_policy = ICompletableItemDefaultRequiredPolicy(parent_course)
        child_policy = ICompletableItemDefaultRequiredPolicy(child_course)
        child_policy2 = ICompletableItemDefaultRequiredPolicy(child_course2)

        assert_that(parent_policy.mime_types, has_length(0))
        assert_that(child_policy.mime_types, has_length(0))
        assert_that(child_policy2.mime_types, has_length(0))

        parent_policy.add_mime_types(['a', 'b'])
        assert_that(parent_policy.mime_types, has_items('a', 'b'))
        assert_that(child_policy.mime_types, has_items('a', 'b'))
        assert_that(child_policy2.mime_types, has_length(0))

        child_policy.add_mime_types(['c'])
        assert_that(parent_policy.mime_types, has_items('a', 'b'))
        assert_that(child_policy.mime_types, has_items('a', 'b', 'c'))
        assert_that(child_policy2.mime_types, has_length(0))

        parent_policy.mime_types.clear()
        assert_that(parent_policy.mime_types, has_length(0))
        assert_that(child_policy.mime_types, has_length(1))
        assert_that(child_policy.child_policy.mime_types, has_items('c'))
        assert_that(child_policy2.mime_types, has_length(0))

        child_policy2.add_mime_types(['e'])
        assert_that(parent_policy.mime_types, has_length(0))
        assert_that(child_policy.mime_types, has_length(1))
        assert_that(child_policy2.mime_types, has_items('e'))
        assert_that(child_policy2.mime_types, has_length(1))
