#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than

from nti.testing.matchers import is_empty
from nti.testing.matchers import validly_provides

from nti.testing.time import time_monotonically_increases

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.activity import _DefaultCourseActivity

from nti.app.products.courseware.interfaces import ICourseInstanceActivity

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestActivity(ApplicationLayerTest):

    @WithMockDSTrans
    @time_monotonically_increases
    def test_activity(self):

        activity = _DefaultCourseActivity()
        assert_that(activity, validly_provides(ICourseInstanceActivity))

        assert_that(list(activity.items()), is_empty())
        assert_that(activity, has_length(0))
        original_lastmod = activity.lastModified
        assert_that(original_lastmod, is_(0))

        class Item(object):
            pass

        item1 = Item()
        item2 = Item()

        iids = component.getUtility(IIntIds)
        iids.register(item1)
        iids.register(item2)

        activity.append(item1)
        activity.append(item2)

        assert_that(activity, has_length(2))
        assert_that(activity, has_property('lastModified',
                                           greater_than(original_lastmod)))

        def get_items():
            return [x[1] for x in activity.items()]
        assert_that(get_items(),
                    is_([item2, item1]))

        activity.remove(item1)
        assert_that(get_items(),
                    is_([item2]))

        del activity._storage  # let the transaction commit
        iids.unregister(item1)
        iids.unregister(item2)
