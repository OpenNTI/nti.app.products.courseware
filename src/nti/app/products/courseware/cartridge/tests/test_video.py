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

from nti.contenttypes.presentation.interfaces import MP4_VIDEO_SOURCE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE_TYPE

from nti.contenttypes.presentation.media import NTIVideo
from nti.contenttypes.presentation.media import NTITranscript
from nti.contenttypes.presentation.media import NTIVideoSource

from nti.dataserver.tests import mock_dataserver


class TestVideo(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_video(self):
        # pylint: disable=too-many-function-args
        archive = tempfile.mkdtemp()
        try:
            with mock_dataserver.mock_db_trans(self.ds) as connection:
                intids = component.getUtility(IIntIds)
                video = NTIVideo()
                connection.add(video)
                # source
                source = NTIVideoSource()
                source.height = source.width = 300
                source.service = YOUTUBE_VIDEO_SERVICE
                source.source = [MP4_VIDEO_SOURCE]
                source.type = [YOUTUBE_VIDEO_SERVICE_TYPE]
                video.sources = [source]

                # transcript
                transcript = NTITranscript()
                transcript.src = u'resources/transcript.vtt'
                video.transcripts = [transcript]

                intids.register(video)
    
                handler = IElementHandler(video, None)
                assert_that(handler, is_not(none()))
                assert_that(handler, validly_provides(IBaseElementHandler))
                assert_that(handler, verifiably_provides(IBaseElementHandler))
                handler.write_to(archive)
                
                transaction.doom()
        finally:
            shutil.rmtree(archive, True)
