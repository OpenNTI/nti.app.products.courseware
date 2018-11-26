#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from bs4 import BeautifulSoup

from pynliner import Pynliner  # TODO add this to buildout deps

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.qti.interfaces import IQTIAssessment
from nti.app.products.courseware.qti.interfaces import IQTIItem

from nti.assessment.interfaces import IQAssessment
from nti.assessment.interfaces import IQEditableEvaluation
from nti.assessment.interfaces import IQuestionSet
from nti.common import random

from nti.contentlibrary.interfaces import IPersistentFilesystemContentUnit
from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


# TODO ideally, on content backed questions we would parse the questions out of the html
# rather than the object. The reasoning behind this is that it would allow us
# to create Canvas text entries for interlaced text content. For now, we are
# using the object questions as it is an implementation that works for both
# content backed and ui created questions, and interlaced text does not have
# an identifying div wrapping it making it difficult to determine a consistent heuristic
# for ripping it out. As such, all interlaced text will be preserved, but will be
# displayed in the assignment body. Because we are leaving all other tags in besides
# object tags, there is a possibility that a future import implementation could
# bring NTI qti exports back in properly
@interface.implementer(IQTIAssessment)
class QTIAssessment(object):

    def __init__(self, context):
        self.context = context
        self.dependencies = {}
        self.items = []
        if not self.is_content_backed:
            # Parse the questions
            for question in self.questions:
                for part in question.parts:
                    qti_item = IQTIItem(part)
                    qi_export = qti_item.to_xml()
                    self.items.append(qi_export)
                    self.dependencies.update(qti_item.dependencies)
            # set the content
            self.content = context.contnet
        else:
            self.content = self._parse_content()

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
        return identifier

    @Lazy
    def context_parent(self):
        return self.context.__parent__

    @Lazy
    def is_content_backed(self):
        return not IQEditableEvaluation.providedBy(self.context_parent) \
               and IPersistentFilesystemContentUnit.providedBy(self.context_parent)

    @Lazy
    def title(self):
        return self.context.title

    @Lazy
    def content_file(self):
        if self.is_content_backed:
            return self.context_parent.key

    def content_soup(self, styled=False):
        if self.is_content_backed:
            text = self.content_file.read_contents_as_text()
            if styled:
                # This inlines external style sheets
                content = Pynliner()
                content.root_url = self.content_file.absolute_path
                assert getattr(content, '_get_url', None)  # If this private method gets refactored, let us know
                # By default, this tries to retrieve via request, we will override
                content._get_url = lambda url: open(url).read().decode()
                content.from_string(text)
                text = content.run()
            return BeautifulSoup(text, features='lxml')

    def _is_internal_resource(self, href):
        return not bool(urllib_parse.urlparse(href).scheme)

    def _parse_content(self):
        """
        Attempt to take a content backed assignment page contents and strip it down for external usage.
        Specifically, object references. We will also attempt to
        build dependencies on any internal resources
        """
        page_contents = self.content_soup().find_all('div', {'class': 'page-contents'})
        new_content = BeautifulSoup()
        to_be_extracted = []  # Because we recurse the structure we need to delay extraction until we are finished
        for pg in page_contents:  # Most likely len(page_contents) == 1
            for tag in pg.recursiveChildGenerator():
                # Check for resource refs and add to dependencies
                if hasattr(tag, 'name') and \
                        tag.name == 'a' and \
                        hasattr(tag, 'attrs') and \
                        'href' in tag.attrs:
                    href = tag.attrs['href']
                    if self._is_internal_resource(href):
                        path_to = os.path.join(self.content_file.bucket.absolute_path, href)
                        href = os.path.join('dependencies', href)
                        self.dependencies[path_to] = href
                        tag.attrs['href'] = os.path.join('$IMS-CC-FILEBASE$', href)
                # Grab images
                if hasattr(tag, 'name') and tag.name == 'img' and \
                        hasattr(tag, 'attrs') and 'src' in tag.attrs:
                    src = tag.attrs['src']
                    if self._is_internal_resource(src):
                        path_to = os.path.join(self.content_file.bucket.absolute_path, src)
                        src = os.path.join('dependencies', src)
                        self.dependencies[path_to] = src
                        tag.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', src)
                # Extract marker anchor tags
                if hasattr(tag, 'name') and \
                        tag.name == 'a' and \
                        hasattr(tag, 'attrs') and \
                        'name' in tag.attrs and \
                        len(tag.attrs) == 1:
                    to_be_extracted.append(tag)
            new_content.append(pg)

        for tag in to_be_extracted:
            tag.extract()

        to_be_extracted = []
        # Strip objects and handle interlaced text
        question_objects = new_content.find_all('object',
                                                {'type': 'application/vnd.nextthought.naquestion'})
        for i, question_object in enumerate(question_objects):
            ntiid = question_object.attrs['data']
            question = find_object_with_ntiid(ntiid)
            assert question in self.questions  # sanity check
            for part in question.parts:
                qti_item = IQTIItem(part)
                self.items.append(qti_item.to_xml())
                self.dependencies.update(qti_item.dependencies)
            nested_text = ''
            try:
                next_question_object = question_objects[i + 1]
                for sibling in question_object.next_siblings:
                    if sibling == next_question_object:
                        break
                    # Skip empty tags
                    if sibling.name is None and sibling.strip() == '':
                        continue
                    nested_text += ' ' + repr(sibling)
                    to_be_extracted.append(sibling)
            except IndexError:
                pass
            # Ok, there was text in between this object and the next. Create a text entry
            if nested_text != '':
                item_identifier = random.generate_random_string()  # Shouldn't need this identifier
                assignment_identifier_ref = random.generate_random_string()  # same as above
                renderer = get_renderer('templates/parts/text_entry', '.pt')
                context = {'item_identifier': item_identifier,
                           'title': 'Text',
                           'assignment_identifier_ref': assignment_identifier_ref,
                           'mattext': nested_text}
                self.items.append(execute(renderer, {'context': context}))
            question_object.extract()

        for tag in to_be_extracted:
            tag.extract()
        return new_content.prettify()

    @Lazy
    def questions(self):
        if IQuestionSet.providedBy(self.context):
            return self.context.questions
        elif IQAssessment.providedBy(self.context):
            # Get q sets from assignment parts
            question_sets = (part.question_set for part in self.context.parts)
            # Coalesce the questions
            return [question for qs in question_sets for question in qs.questions]
        else:
            # Should never happen TODO handle
            return None

    def export(self):
        renderer = get_renderer('qti_assessment', '.pt')
        context = {'ident': self.identifier,
                   'title': self.context.title,
                   'items': self.items}
        return execute(renderer, {'context': context})


class CanvasAssessmentMeta(object):

    def __init__(self, assessment):
        self.assessment = assessment

    def meta(self):
        renderer = get_renderer('assessment_meta', '.pt')
        context = {'title': self.assessment.title,
                   'description': self.assessment.content,
                   'quiz_id': self.assessment.identifier}
        return execute(renderer, {'context': context})
