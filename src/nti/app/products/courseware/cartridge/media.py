#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

import six

from collections import defaultdict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.interfaces import ICanvasWikiContent
from nti.app.products.courseware.cartridge.interfaces import IIMSResource
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.presentation.interfaces import KALTURA_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import VIMEO_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import YOUTUBE_VIDEO_SERVICE
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTITranscript
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIVideoRoll

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


UICONF_ID_MAP = {'1500101': '30404512',
                '1459281': '15084112'}


@interface.implementer(IIMSWebContentUnit)
@component.adapter(INTITranscript)
class IMSWebContentTranscript(AbstractIMSWebContent):

    extension = '.vtt'

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

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


@interface.implementer(IIMSWebContentUnit, ICanvasWikiContent)
@component.adapter(INTIVideoRoll)
class IMSWebContentVideoRoll(AbstractIMSWebContent):

    extension = '.html'

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    def _process_videos(self, videos):
        if videos:
            for video in videos:
                concrete_video = IConcreteAsset(video)
                self.dependencies['videos'].append(IIMSResource(concrete_video))
        return self.dependencies

    @Lazy
    def filename(self):
        return unicode(self.identifier) + self.extension

    @Lazy
    def dirname(self):
        return unicode(self.identifier)

    def export(self, dirname):
        self._process_videos(self.context.Items)
        renderer = get_renderer("video_roll", ".pt")
        title = self.context.title
        if not title:
            lesson = self.context.__parent__.__parent__  # Overview Group => Lesson
            assert INTILessonOverview.providedBy(lesson)  # If this invariant changes in the future, blow up
            title = u'Videos (%s)' % lesson.title
        context = {
            'identifier': self.identifier,
            'title': title,
            'videos': self.dependencies['videos']
        }
        html = execute(renderer, {"context": context})
        target = os.path.join(dirname, self.dirname, self.filename)
        self.write_resource(target, html)


@interface.implementer(IIMSWebContentUnit, ICanvasWikiContent)  # Mark as wiki content for export
@component.adapter(INTIVideo)
class IMSWebContentVideo(AbstractIMSWebContent):
    """
    Video urls MUST be 'https' urls to be compatible in canvas
    """

    extension = '.html'
    _dependencies = defaultdict(list)

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    def _process_transcript(self, transcripts):
        if transcripts:
            for transcript in transcripts:
                content = IIMSResource(transcript)
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
            'width': self.width,
            'height': self.height,
            'transcript': None,
            'identifier': self.identifier,
            'title': self.context.title
        }
        if self.dependencies:
            context['transcript'] = 'transcripts/' + self.dependencies.get('transcripts')[0].filename
        return execute(renderer, {"context": context})

    def kaltura(self, default_uiconf_id="15491291"):
        """
        Return a string that represent a kaltura video file
        resource in a cartridge
        """
        partner_id, entry_id = self.source_id.split(':')
        uiconf_id = UICONF_ID_MAP.get(partner_id, default_uiconf_id)
        src_href = 'https://cdnapisec.kaltura.com/p/%s/sp/%s00/embedIframeJs/uiconf_id/%s/partner_id/%s?iframeembed=true&playerId=nti_1544225341&entry_id=%s' % (partner_id,
                                                                                                                                                                 partner_id,
                                                                                                                                                                 uiconf_id,
                                                                                                                                                                 partner_id,
                                                                                                                                                                 entry_id)
        renderer = get_renderer("video_kaltura", ".pt")
        context = {
            'style': 'height: %spx; width: %spx' % (self.source.height, self.source.width),
            'width': self.width,
            'height': self.height,
            'transcript': None,
            'src': src_href,
            'identifier': self.identifier,
            'title': self.context.title
        }
        if UICONF_ID_MAP.get(partner_id, None) is None:
            context['missing_uiconf'] = True
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
            'width': self.width,
            'height': self.height,
            'transcript': None,
            'identifier': self.identifier,
            'title': self.context.title
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
    def width(self):
        return self.source.width or 640

    @Lazy
    def height(self):
        return self.source.height or 385

    @Lazy
    def source_id(self):
        source_id = next(iter(self.source.source))
        return source_id

    @Lazy
    def filename(self):
        return unicode(self.identifier) + self.extension

    @Lazy
    def dirname(self):
        return unicode(self.identifier)
