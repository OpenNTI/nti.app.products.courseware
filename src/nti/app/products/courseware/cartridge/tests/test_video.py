#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods
import unittest

from hamcrest import none, is_, has_length
from hamcrest import is_not
from hamcrest import assert_that

from nti.app.products.courseware.cartridge.tests import CommonCartridgeLayerTest
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

does_not = is_not

import transaction

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import VIMEO_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE_TYPE
from nti.contenttypes.presentation.interfaces import VIMEO_VIDEO_SERVICE_TYPE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE_TYPE

from nti.contenttypes.presentation.media import NTIVideo
from nti.contenttypes.presentation.media import NTITranscript
from nti.contenttypes.presentation.media import NTIVideoSource


class TestVideo(CommonCartridgeLayerTest):

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    def _test_video(self, video):
        video_intid = self.intids.queryId(video)

        web_content = IIMSWebContentUnit(video)
        assert_that(web_content, is_not(none()))
        assert_that(web_content, validly_provides(IIMSWebContentUnit))
        assert_that(web_content, verifiably_provides(IIMSWebContentUnit))

        # Check identifier
        assert_that(web_content.identifier, is_(video_intid))
        assert_that(web_content.__name__, is_(video_intid))

        # Test file attributes
        with web_content.export() as cc_file:
            assert_that(cc_file.name, is_('%s%s' % (web_content.identifier, web_content.extension)))

        # Test dependencies
        deps = web_content.dependencies
        transcripts = deps.get('transcripts')
        assert_that(transcripts, has_length(1))
        assert_that(transcripts[0], validly_provides(IIMSWebContentUnit))
        assert_that(transcripts[0], verifiably_provides(IIMSWebContentUnit))

    @WithMockDSTrans
    def test_youtube_video(self):
        video = NTIVideo()
        # source
        source = NTIVideoSource()
        source.height = source.width = 300
        source.service = YOUTUBE_VIDEO_SERVICE
        source.source = [u"oYG7iX3eRbM"]
        source.type = [YOUTUBE_VIDEO_SERVICE_TYPE]
        video.sources = [source]

        # transcript
        transcript = NTITranscript()
        transcript.src = u'resources/transcript.vtt'
        video.transcripts = [transcript]

        self.intids.register(video)
        self.intids.register(transcript)

        self._test_video(video)

    @WithMockDSTrans
    def test_vimeo_video(self):
        video = NTIVideo()
        # source
        source = NTIVideoSource()
        source.height = source.width = 300
        source.service = VIMEO_VIDEO_SERVICE
        source.source = [u"123123"]
        source.type = [VIMEO_VIDEO_SERVICE_TYPE]
        video.sources = [source]

        # transcript
        transcript = NTITranscript()
        transcript.src = u'resources/transcript.vtt'
        video.transcripts = [transcript]

        self.intids.register(video)
        self.intids.register(transcript)

        self._test_video(video)

    @WithMockDSTrans
    def test_kaltura_video(self):
        # pylint: disable=too-many-function-args
        video = NTIVideo()
        # source
        source = NTIVideoSource()
        source.height = source.width = 300
        source.service = KALTURA_VIDEO_SERVICE
        source.source = [u"1500101:0_hwfe5zjr"]
        source.type = [KALTURA_VIDEO_SERVICE_TYPE]
        video.sources = [source]

        # transcript
        transcript = NTITranscript()
        transcript.src = u'resources/transcript.vtt'
        video.transcripts = [transcript]

        self.intids.register(video)
        self.intids.register(transcript)

        self._test_video(video)

