#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import json
import os

from zope import component, interface
from zope.cachedescriptors.property import Lazy
from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit, ICanvasWikiContent
from nti.app.products.courseware.cartridge.renderer import get_renderer, execute
from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent
from nti.contentlibrary.interfaces import IContentPackage
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.traversal.traversal import find_interface

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit, ICanvasWikiContent)
@component.adapter(INTITimeline)
class IMSWebContentTimelineWrapper(AbstractIMSWebContent):

    extension = '.html'

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def filename(self):
        return unicode(self.identifier) + self.extension

    def export(self, dirname):
        # Create the actual timeline. We then wrap in an iframe so canvas leaves our js alone
        self.dependencies['timelines'].append(IMSWebContentTimeline(self.context))
        renderer = get_renderer("timeline_wrapper", ".pt")
        title = self.context.label
        context = {
            'identifier': self.identifier,
            'title': title,
            'timeline': self.dependencies['timelines'][0].filename  # Should only be one
        }
        html = execute(renderer, {"context": context})
        target = os.path.join(dirname, self.filename)
        self.write_resource(target, html)


class IMSWebContentTimeline(AbstractIMSWebContent):

    extension = '.html'

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def filename(self):
        return unicode(self.identifier) + self.extension

    @Lazy
    def json(self):
        href = self.context.href
        content_package = find_interface(self.context, IContentPackage)
        path = os.path.join(content_package.root.absolute_path, href)
        with open(path, 'r') as json_file:
            json_data = json_file.read()
        return json.dumps(json.loads(json_data))  # Remove pretty print

    def export(self, dirname):
        renderer = get_renderer("timeline", ".pt")
        context = {
            'json': self.json
        }
        html = execute(renderer, {"context": context})
        target = os.path.join(dirname, self.filename)
        self.write_resource(target, html)
