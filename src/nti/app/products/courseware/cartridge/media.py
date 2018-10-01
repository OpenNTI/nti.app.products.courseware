#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil

from xml.dom import minidom

import six

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.interfaces import IElementHandler

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITranscript

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)

# transcripts


@component.adapter(INTITranscript)
class TranscriptHandler(AbstractElementHandler):

    def iter_items(self):
        return ()

    def resource_node(self):
        transcript = self.context
        if not isinstance(transcript.src, six.string_types):
            # ATM we don't support authored transcripts
            doc_root = None
        else:
            DOMimpl = minidom.getDOMImplementation()
            xmldoc = DOMimpl.createDocument(None, "resource", None)
            doc_root = xmldoc.documentElement
            doc_root.setAttribute("type", "webcontent")
            doc_root.setAttribute("identifier", "%s" % self.identifier)
            doc_root.setAttribute("href", "%s" % transcript.src)
            # file
            node = xmldoc.createElement("file")
            node.setAttributeNS(None, "href", "%s" % transcript.src)
            doc_root.appendChild(node)
        return doc_root

    def iter_resources(self):
        node = self.resource_node()
        return (node,) if node is not None else ()

    # cartridge

    @property
    def track(self):
        """
        Return the source for the transcript file
        """
        transcript = self.context
        if isinstance(transcript.src, six.string_types):
            # The source is the relative location in the
            # content package; it should be saved in the
            # same relative location in the cartridge
            return transcript.src

    def write_to(self, archive):
        transcript = self.context
        # find content package and copy the transcript file
        package = find_interface(transcript, IContentPackage, strict=False)
        if package is None:
            logger.warning("Could not find content package for %s", transcript)
        elif isinstance(transcript.src, six.string_types):
            root = package.root
            if not IFilesystemBucket.providedBy(root):
                logger.warning("Unsupported bucket Boto?")
            else:
                source_path = os.path.join(root.absolute_path,
                                           transcript.src)
                target_path = os.path.join(archive,
                                           transcript.src)
                dirname = os.path.dirname(target_path)
                if os.path.exists(dirname):
                    os.makedirs(dirname)
                shutil.copy(source_path, target_path)


# video

def youtube_element(video):
    """
    Return a string that represent a youtube video file 
    resource in a cartrige
    """
    source = next(iter(video.sources))  # required
    source_id = next(iter(source.source))  # required
    src_href = "https://www.youtube.com/embed/%s?rel=0" % source_id
    renderer = get_renderer("video_youtube", ".pt")
    context = {
        'style': 'padding: 20px',
        'src': src_href,
        'width': source.width,
        'height': source.height,
        "frameborder": '0',
        "allow": 'autoplay; encrypted-media',
        'transcript': None,
    }
    # track
    if video.transcripts:
        for transcript in video.transcripts:
            handler = IElementHandler(transcript, None)
            track = getattr(handler, "track", None)
            if track:
                context['transcript'] = track
                break
    return execute(renderer, {"context": context})


DEFAULT_KALTURA_SRC = """
https://cdnapisec.kaltura.com/p/{{partner_id}}/sp/{{partner_id}}00/embedIframeJs/
uiconf_id/{{uiconf_id}}/partner_id/{{partner_id}}?autoembed=true&entry_id={{entry_id}}
&playerId=kaltura_player_1377036702&cache_st=1377036702&width={{width}}&height={{height}}"
"""


def kaltura_element(video, uiconf_id="15491291"):
    """
    Return a string that represent a kaltura video file 
    resource in a cartrige
    """
    source = next(iter(video.sources))  # required
    source_id = next(iter(source.source))  # required
    entry_id, partner_id = source_id.split(':')
    renderer = get_renderer("video_kaltura", ".pt")
    context = {
        'style': 'padding: 20px',
        'transcript': None,
    }
    # script
    kaltura_src = DEFAULT_KALTURA_SRC.replace(r'\n', '')
    kaltura_src = kaltura_src.replace("{{entry_id}}", entry_id)
    kaltura_src = kaltura_src.replace("{{uiconf_id}}", uiconf_id)
    kaltura_src = kaltura_src.replace("{{partner_id}}", partner_id)
    kaltura_src = kaltura_src.replace("{{width}}", str(source.width))
    kaltura_src = kaltura_src.replace("{{height}}", str(source.height))
    context['src'] = kaltura_src.strip()
    # track
    if video.transcripts:
        for transcript in video.transcripts:
            handler = IElementHandler(transcript, None)
            track = getattr(handler, "track", None)
            if track:
                context['transcript'] = track
                break
    return execute(renderer, {"context": context})


@component.adapter(INTIVideo)
class VideoHandler(AbstractElementHandler):

    def iter_items(self):
        return ()

    def resource_node(self):
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "resource", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttribute("type", "webcontent")
        doc_root.setAttribute("identifier", "%s" % self.identifier)
        doc_root.setAttribute("href", "content/%s.html" % self.identifier)
        # file
        node = xmldoc.createElement("file")
        node.setAttributeNS(None, "href", "content/%s.html" % self.identifier)
        doc_root.appendChild(node)
        return doc_root

    def iter_resources(self):
        return (self.resource_node(),)

    # cartridge

    def youtube(self, video):
        return youtube_element(video)

    def kaltura(self, video):
        return kaltura_element(video)

    def video_element(self):
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
                logger.warning("Unsupported Video Service %s",
                               video.ntiid)
        return result

    def write_to(self, archive):
        video = self.video_element()
        if video is not None:
            # write the html file under the content
            # directory
            path = os.path.join(archive, "content",
                                "%s.html" % self.identifier)
            dirname = os.path.dirname(path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(os.path.join(path), "w") as fp:
                fp.write(video)


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
