#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import time

import six

from collections import defaultdict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit, ICanvasWikiContent

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import VIMEO_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITranscript

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit)
@component.adapter(INTITranscript)
class IMSWebContentTranscript(AbstractIMSWebContent):

    extension = '.vtt'

    def export(self, path):
        package = find_interface(self.context, IContentPackage, strict=False)
        if package is None:
            logger.warning("Could not find content package for %s", self.context)
        elif isinstance(self.context.src, six.string_types):
            root = package.root
            if not IFilesystemBucket.providedBy(root):
                logger.warning("Unsupported bucket Boto?")
                return None  # TODO how do we want to handle this
            else:
                source_path = os.path.join(root.absolute_path,
                                           self.context.src)
                fname = os.path.basename(source_path)
                target_path = os.path.join(path, fname)
                self.copy_resource(source_path, target_path)

    @Lazy
    def filename(self):
        return os.path.basename(self.context.src)


@interface.implementer(IIMSWebContentUnit)
@component.adapter(INTIVideo)
class IMSWebContentVideo(AbstractIMSWebContent):
    """
    Video urls MUST be 'https' urls to be compatible in canvas
    """

    extension = '.html'
    _dependencies = defaultdict(list)

    def __init__(self, asset):
        super(IMSWebContentVideo, self).__init__(asset)
        interface.alsoProvides(self, ICanvasWikiContent)

    def _process_transcript(self, transcripts):
        if transcripts:
            for transcript in transcripts:
                content = IIMSWebContentUnit(transcript)
                return content
        return None

    def youtube(self):
        """
        Return a string that represent a youtube video file
        resource in a cartridge
        """
        src_href = "https://www.youtube.com/embed/%s?rel=0" % self.source_id
        renderer = get_renderer("video_youtube", ".pt")
        context = {
            'style': 'height: %spx; width: %spx' % (self.source.height, self.source.width),
            'src': src_href,
            'width': self.source.width,
            'height': self.source.height,
            'transcript': None,
        }
        if self.dependencies:
            context['transcript'] = 'transcripts/' + self.dependencies.get('transcripts')[0].filename
            context['transcript'] = 'transcripts/' + self.dependencies.get('transcripts')[0].filename
        return execute(renderer, {"context": context})

    def kaltura(self, uiconf_id="15491291"):
        """
        Return a string that represent a kaltura video file
        resource in a cartridge
        """
        # TODO Update template to iframe instead of script
        current = int(time.time())
        partner_id, entry_id = self.source_id.split(':')
        player_id = 'nti_%s' % current
        src_href = 'https://www.kaltura.com/p/%s/sp/%s00/embedIframeJs/uiconf_id/%s/partner_id/%s' \
                   '?iframeembed=true&playerId=%s&entry_id=%s' \
                   % (partner_id, partner_id, uiconf_id, partner_id, player_id, entry_id)
        renderer = get_renderer("video_kaltura", ".pt")
        context = {
            'style': 'height: %spx; width: %spx' % (self.source.height, self.source.width),
            'width': self.source.width,
            'height': self.source.height,
            'transcript': None,
            'src': src_href
        }
        if self.dependencies:
            context['transcript'] = 'transcripts/' + self.dependencies.get('transcripts')[0].filename
        return execute(renderer, {"context": context})

    def vimeo(self):
        """
        Return a string that represents a vimeo video file
        resource in a cartridge
        """
        src_href = "https://player.vimeo.com/video/%s?embedparameter=value" % self.source_id
        renderer = get_renderer("video_vimeo", ".pt")
        context = {
            'style': 'height: %spx; width: %spx' % (self.source.height, self.source.width),
            'src': src_href,
            'width': self.source.width,
            'height': self.source.height,
            'transcript': None,
        }
        if self.dependencies:
            context['transcript'] = 'transcripts/' + self.dependencies.get('transcripts')[0].filename
        return execute(renderer, {"context": context})

    def export(self, dirname):
        if self.source.service == YOUTUBE_VIDEO_SERVICE:
            html = self.youtube()
        elif self.source.service == KALTURA_VIDEO_SERVICE:
            html = self.kaltura()
        elif self.source.service == VIMEO_VIDEO_SERVICE:
            html = self.vimeo()
        else:
            raise NotImplementedError
        path = os.path.join(dirname, self.filename)
        self.write_resource(path, html)

    @Lazy
    def dependencies(self):
        transcript_content = self._process_transcript(self.context.transcripts)
        if transcript_content:
            self._dependencies['transcripts'] = [transcript_content]
        return self._dependencies

    @Lazy
    def source(self):
        source_type = next(iter(self.context.sources))
        return source_type

    @Lazy
    def source_id(self):
        source_id = next(iter(self.source.source))
        return source_id

    @Lazy
    def filename(self):
        # TODO this is going to cause problems...
        filename = '%s%s' % (self.context.title, self.extension)
        if self.dependencies:
            return '%s/%s' % (self.context.title, filename)
        return filename

    @Lazy
    def dirname(self):
        # TODO may want to use intid to avoid collisions
        if self.dependencies:
            return self.context.title
        return None
