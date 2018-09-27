#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from xml.dom import minidom

import six

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.interfaces import IElementHandler

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler

from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITranscript

from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


@component.adapter(INTITranscript)
class TranscriptHandler(AbstractElementHandler):

    def iter_nodes(self):
        return ()

    # cartridge

    @property
    def track(self):
        """
        Return a minidom for the topic file
        """
        transcript = self.context
        if isinstance(transcript.src, six.string_types):
            # The source is the relative location in the
            # content package; it should be saved in the
            # same relative location in the cartridge
            DOMimpl = minidom.getDOMImplementation()
            xmldoc = DOMimpl.createDocument(None, "track", None)
            doc_root = xmldoc.documentElement
            doc_root.setAttribute("src", transcript.src)
            return doc_root

    def write(self):
        """
        Write the necesary files to the archive
        """


def youtube_element(video):
    DOMimpl = minidom.getDOMImplementation()
    xmldoc = DOMimpl.createDocument(None, "html", None)
    doc_root = xmldoc.documentElement
    body = xmldoc.createElement("body")
    body.setAttribute("style", "padding: 20px")
    doc_root.appendChild(body)
    # source
    source = next(iter(video.sources))  # required
    source_id = next(iter(source.source))  # required
    # iframe
    iframe = xmldoc.createElement("iframe")
    iframe.setAttribute("src",
                        "https://www.youtube.com/embed/%s?rel=0" % source_id)
    iframe.setAttribute("width", str(source.width))
    iframe.setAttribute("height", str(source.height))
    iframe.setAttribute("frameborder", "0")
    iframe.setAttribute("allow", "autoplay; encrypted-media")
    body.appendChild(iframe)
    # track
    if video.transcripts:
        for transcript in video.transcripts:
            handler = IElementHandler(transcript, None)
            track = getattr(handler, "track", None)
            if track is not None:
                body.appendChild(track)
                track_set = True
                break
        if not track_set:
            logger.warning("Unsupported transcript source(s) for video %s",
                           video.ntiid)
    return doc_root


DEFAULT_KALTURA_SRC = """
https://cdnapisec.kaltura.com/p/{{partner_id}}/sp/{{partner_id}}00/embedIframeJs/
uiconf_id/{{uiconf_id}}/partner_id/{{partner_id}}?autoembed=true&entry_id={{entry_id}}
&playerId=kaltura_player_1377036702&cache_st=1377036702&width={{width}}&height={{height}}"
"""


def kaltura_element(video, uiconf_id="15491291"):
    DOMimpl = minidom.getDOMImplementation()
    xmldoc = DOMimpl.createDocument(None, "html", None)
    doc_root = xmldoc.documentElement
    body = xmldoc.createElement("body")
    body.setAttribute("style", "padding: 20px")
    doc_root.appendChild(body)
    # source
    source = next(iter(video.sources))  # required
    source_id = next(iter(source.source))  # required
    entry_id, partner_id = source_id.split(':')
    # script
    kaltura_src = DEFAULT_KALTURA_SRC.replace(r'\n', '')
    kaltura_src = kaltura_src.replace("{{entry_id}}", entry_id)
    kaltura_src = kaltura_src.replace("{{uiconf_id}}", uiconf_id)
    kaltura_src = kaltura_src.replace("{{partner_id}}", partner_id)
    kaltura_src = kaltura_src.replace("{{width}}", str(source.width))
    kaltura_src = kaltura_src.replace("{{height}}", str(source.height))
    script = xmldoc.createElement("script")
    script.setAttribute("src", kaltura_src)
    body.appendChild(script)
    # track
    if video.transcripts:
        for transcript in video.transcripts:
            handler = IElementHandler(transcript, None)
            track = getattr(handler, "track", None)
            if track is not None:
                body.appendChild(track)
                track_set = True
                break
        if not track_set:
            logger.warning("Unsupported transcript source(s) for video %s",
                           video.ntiid)
    return doc_root


@component.adapter(INTIVideo)
class VideoHandler(AbstractElementHandler):

    def iter_nodes(self):
        return ()

    # cartridge

    def youtube(self, video):
        return youtube_element(video)

    def kaltura(self, video):
        return kaltura_element(video)

    def video(self):
        """
        Return a minidom for the video file
        """
        result = None
        video = self.context
        if video.sources:
            source = next(iter(video.sources))  # pick first
            if source.service == YOUTUBE_VIDEO_SERVICE:
                result = self.youtube(video)
            elif source.service == KALTURA_VIDEO_SERVICE:
                result = self.kaltura(video)
            else:
                logger.warning("Unsupported Video %s", video.ntiid)
        return result

    def write(self):
        """
        Write the necesary files to the archive
        """


@component.adapter(INTIVideoRef)
class VideoRefHandler(AbstractElementHandler):

    @Lazy
    def video(self):
        return find_object_with_ntiid(self.context.target)

    def iter_resources(self):
        return ()

    # cartridge

    def write(self):
        """
        Write the necesary files to the archive
        """
