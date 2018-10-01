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

import shutil
import tempfile

import transaction

from zope import component

from zope.intid.interfaces import IIntIds

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.cartridge.interfaces import IElementHandler
from nti.app.products.courseware.cartridge.interfaces import IBaseElementHandler

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.presentation.discussion import NTIDiscussionRef

from nti.dataserver.contenttypes.forums.forum import GeneralForum

from nti.dataserver.contenttypes.forums.post import GeneralHeadlinePost

from nti.dataserver.contenttypes.forums.topic import GeneralHeadlineTopic

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.oids import to_external_ntiid_oid


class TestDiscussion(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_forums(self):
        archive = tempfile.mkdtemp()
        try:
            with mock_dataserver.mock_db_trans(self.ds) as connection:
                intids = component.getUtility(IIntIds)
                forum = GeneralForum()
                connection.add(forum)
                intids.register(forum)
    
                headline = GeneralHeadlinePost()
                headline.body = [u'bleach']
                connection.add(forum)
                intids.register(headline)

                topic = GeneralHeadlineTopic()
                headline.__parent =  topic
                topic.headline = headline
                connection.add(topic)
                forum['mytopic'] = topic
                
                handler = IElementHandler(topic, None)
                assert_that(handler, is_not(none()))
                assert_that(handler, validly_provides(IBaseElementHandler))
                assert_that(handler, verifiably_provides(IBaseElementHandler))
                # pylint: disable=too-many-function-args
                handler.write_to(archive)

                ref = NTIDiscussionRef()
                ref.target = to_external_ntiid_oid(topic)
                connection.add(ref)
                intids.register(ref)

                handler = IElementHandler(ref, None)
                assert_that(handler, is_not(none()))
                assert_that(handler, validly_provides(IBaseElementHandler))
                assert_that(handler, verifiably_provides(IBaseElementHandler))
                handler.write_to(archive)
                
                # remove to avoid DBs conflicts
                del forum['mytopic']
                intids.unregister(ref)
                intids.unregister(forum)
                transaction.doom()
        finally:
            shutil.rmtree(archive, True)
