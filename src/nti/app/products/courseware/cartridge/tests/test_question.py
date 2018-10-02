#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
does_not = is_not

import transaction

from zope import component

from zope.intid.interfaces import IIntIds

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.cartridge.interfaces import IElementHandler
from nti.app.products.courseware.cartridge.interfaces import IBaseElementHandler

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contentfragments.interfaces import ISanitizedHTMLContentFragment

from nti.assessment.parts import QFreeResponsePart

from nti.assessment.question import QQuestion

from nti.dataserver.tests import mock_dataserver


class TestQuestion(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_free_response(self):
        with mock_dataserver.mock_db_trans(self.ds) as connection:
            intids = component.getUtility(IIntIds)
            question = QQuestion()
            connection.add(question)
            part = QFreeResponsePart()
            part.content = ISanitizedHTMLContentFragment(u'my content')
            question.parts = [part]
            intids.register(question)

            handler = IElementHandler(part, None)
            assert_that(handler, is_not(none()))
            assert_that(handler, validly_provides(IBaseElementHandler))
            assert_that(handler, verifiably_provides(IBaseElementHandler))

            handler.write_to()
            transaction.doom()
