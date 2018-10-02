#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.assessment.interfaces import IQEvaluation
from nti.assessment.interfaces import IQNonGradableFreeResponsePart

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)

# parts


@component.adapter(IQNonGradableFreeResponsePart)
class FreeResponsePartHandler(AbstractElementHandler):

    @Lazy
    def evaluation(self):
        return find_interface(self.context, IQEvaluation, strict=False)

    def iter_items(self):
        return ()

    def iter_resources(self):
        return ()

    # cartridge

    @property
    def title(self):
        return u''

    @property
    def ident(self):
        # pylint: disable=no-member
        return 'ip%s' % self.intids.queryId(self.evaluation)

    @property
    def content(self):
        result = self.context.content or getattr(self.evaluation, 'content', None)
        return self.safe_xml_text(result or u'')

    def item(self):
        """
        Return the item source for this part
        """
        renderer = get_renderer("question_part_essay", ".pt")
        context = {
            'ident': self.ident,
            'title': self.title,
            'mattext': self.content,
        }
        return execute(renderer, {"context": context})

    def write_to(self, unused_archive=None):
        self.item()
