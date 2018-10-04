#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import namedtuple

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.assessment.interfaces import IQEvaluation
from nti.assessment.interfaces import IQNonGradablePart
from nti.assessment.interfaces import IQMultipleChoicePart
from nti.assessment.interfaces import IQNonGradableFreeResponsePart
from nti.assessment.interfaces import IQNonGradableMultipleChoicePart

from nti.base._compat import text_

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)

# parts


@component.adapter(IQNonGradablePart)
class AbstractResponsePartHandler(AbstractElementHandler):

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
        return 'p%s' % self.intids.queryId(self.evaluation)

    @property
    def content(self):
        result = self.context.content \
              or getattr(self.evaluation, 'content', None)
        return self.safe_xml_text(result or u'')

    def qti_item(self, package=None):
        """
        Return the item source for this part
        """
        raise NotImplementedError()

    def write_to(self, unused_archive=None):
        print(self.qti_item())


@component.adapter(IQNonGradableFreeResponsePart)
class FreeResponsePartHandler(AbstractResponsePartHandler):

    def qti_item(self, package=None):
        renderer = get_renderer("question_part_essay", ".pt", package)
        context = {
            'ident': self.ident,
            'title': self.title,
            'mattext': self.content,
        }
        return execute(renderer, {"context": context})


@component.adapter(IQNonGradableMultipleChoicePart)
class NonGradableMultipleChoicePartHandler(AbstractResponsePartHandler):

    Label = namedtuple('Label', ['ident', 'mattext'])

    @property
    def template_name(self):
        return "question_part_multiple_choice"

    @property
    def labels(self):
        return [
            self.Label(text_(i), self.to_plain_text(x)) for i, x in enumerate(self.context.choices)
        ]

    def template_context(self):
        context = {
            'ident': self.ident,
            'title': self.title,
            'mattext': self.content,
            'labels': self.labels,
        }
        return context

    def qti_item(self, package=None):
        renderer = get_renderer(self.template_name, ".pt", package)
        context = self.template_context()
        return execute(renderer, {"context": context})


@component.adapter(IQMultipleChoicePart)
class MultipleChoicePartHandler(NonGradableMultipleChoicePartHandler):

    @property
    def template_name(self):
        return "question_part_multiple_choice"

    @property
    def respident(self):
        sols = self.context.solutions
        return getattr(sols[0], 'value', sols[0]) if sols else None

    def template_context(self):
        context = super(MultipleChoicePartHandler, self).template_context()
        respident = self.respident
        if respident is not None:
            context['respident'] = text_(respident)
        return context

    def qti_item(self, package=None):
        renderer = get_renderer(self.template_name, ".pt", package)
        context = self.template_context()
        return execute(renderer, {"context": context})
