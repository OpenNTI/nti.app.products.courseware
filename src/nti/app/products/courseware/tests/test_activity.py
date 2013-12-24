#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

from zope import component
from zope.intid.interfaces import IIntIds

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_length
from hamcrest import has_property


from nti.testing import base
from nti.testing.time import time_monotonically_increases
from nti.testing.matchers import is_empty

setUpModule = lambda: base.module_setup(set_up_packages=(__name__,))
tearDownModule = base.module_teardown

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from ..activity import _DefaultCourseActivity

@WithMockDSTrans
@time_monotonically_increases
def test_activity():

	activity = _DefaultCourseActivity()

	assert_that( list(activity.items()), is_empty() )
	assert_that( activity, has_length(0) )
	assert_that( activity, has_property('lastModified', 0))
	class Item(object):
		pass

	item1 = Item()
	item2 = Item()

	iids = component.getUtility(IIntIds)
	iids.register(item1)
	iids.register(item2)

	activity.append(item1)
	activity.append(item2)

	assert_that( activity, has_length(2))
	assert_that( activity, has_property('lastModified', 3.0))
	assert_that( list(activity.items()),
				 is_( [(3.0, item2),
					   (2.0, item1)] ))

	activity.remove(item1)
	assert_that( list(activity.items()),
				 is_( [(3.0, item2)] ) )

	del activity._storage # let the transaction commit
	iids.unregister(item1)
	iids.unregister(item2)
