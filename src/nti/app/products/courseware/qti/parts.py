#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from collections import defaultdict
from collections import namedtuple

from bs4 import BeautifulSoup

from six.moves import urllib_parse

from zope import component, interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.qti.interfaces import IQTIItem

from nti.common._compat import text_

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IQTIItem)
class AbstractQTIQuestion(object):

    def __init__(self, part):
        self.context = part
        self.dependencies = {}  # TODO refactor to defaultdict

    @Lazy
    def question(self):
        return self.context.question

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @Lazy
    def item_identifier(self):
        return self.intids.register(self.context)

    @Lazy
    def assignment_identifier_ref(self):
        """
        This is the identifier for this in the non_cc_assessments
        """
        return self.intids.register(self)

    @property
    def base_template_context(self):
        # type: () -> dict
        template_context = {'item_identifier': self.item_identifier,
                            'assignment_identifier_ref': self.assignment_identifier_ref}
        return template_context

    def _is_internal_resource(self, href):
        return not bool(urllib_parse.urlparse(href).scheme)

    @Lazy
    def content(self):
        """
        The relationship between questions and question parts as to where the actual
        question content is stored is inconsistent. We will attempt to remedy this by
        preferring the question content, and deferring to the part content if it doesn't
        exist. Additionally, once the content is found we will try to patch any
        images into the dependencies.
        """
        content = self.question.content
        # we want to use html.parser here so <html> and <body> tags aren't inserted
        content_soup = BeautifulSoup(content, features='html.parser')
        # Check if there is only one anchor tag with no other text
        if len(content_soup.find_all()) == 1 and content_soup.find_all()[0].encode('utf-8') == content_soup.encode('utf-8'):
            # If it is only an anchor we want to use the part content
            for tag in content_soup.recursiveChildGenerator():
                if hasattr(tag, 'name') and tag.name == 'a':
                    content = self.context.content
                    content_soup = BeautifulSoup(content, features='html.parser')
                    break
        elif len(content_soup.find_all()) == 0:
            # If its empty also use the part content
            content = self.context.content
            content_soup = BeautifulSoup(content, features='html.parser')
        for tag in content_soup.recursiveChildGenerator():
            if hasattr(tag, 'name') and tag.name == 'a' and\
               hasattr(tag, 'attrs') and 'href' in tag.attrs:
                href = tag.attrs['href']
                if self._is_internal_resource(href):
                    path_to = os.path.join(self.question.__parent__.key.bucket.absolute_path, href)
                    href = os.path.join('dependencies', href)
                    self.dependencies[path_to] = href
                    tag.attrs['href'] = os.path.join('$IMS-CC-FILEBASE$', href)
            if hasattr(tag, 'name') and tag.name == 'img' and \
               hasattr(tag, 'attrs') and 'src' in tag.attrs:
                src = tag.attrs['src']
                if self._is_internal_resource(src):
                    path_to = os.path.join(self.question.__parent__.key.bucket.absolute_path, src)
                    src = os.path.join('dependencies', src)
                    self.dependencies[path_to] = src
                    tag.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', src)
        return content_soup.prettify()


class QTIMultipleChoice(AbstractQTIQuestion):

    title = u'Multiple Choice'
    Label = namedtuple('Label', ['ident', 'mattext'])

    @property
    def labels(self):
        return [
            self.Label(text_(unicode(i)), x) for i, x in enumerate(self.context.choices)
        ]

    @property
    def respident(self):
        sols = self.context.solutions
        if len(sols) > 1:
            logger.info(u'More than one solution')  # TODO handle
        return getattr(sols[0], 'value', sols[0]) if sols else None

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/multiple_choice', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        context['labels'] = self.labels
        if self.respident:
            context['respident'] = self.respident
        return execute(renderer, {'context': context})


class QTIMultipleAnswers(AbstractQTIQuestion):

    title = u'Multiple Answers'
    Choice = namedtuple('Choice', ['ident', 'mattext'])

    @property
    def choices(self):
        # TODO may need sanitized
        return [
            self.Choice(text_(unicode(i)), x) for i, x in enumerate(self.context.choices)
        ]

    @property
    def answers(self):
        sols = self.context.solutions
        if not sols:
            return None
        if len(sols) > 1:
            logger.info(u'More than one solution')  # TODO handle
        sol_dict = defaultdict(list)
        for val in sols[0].value:
            sol_dict['true'].append(val)
        for val in (x for x in xrange(len(self.choices)) if x not in sols[0].value):
            sol_dict['false'].append(val)
        return sol_dict

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/multiple_answer', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        context['choices'] = self.choices
        if self.answers:
            context['answers'] = self.answers
        return execute(renderer, {'context': context})


class QTIMath(AbstractQTIQuestion):
    pass


class QTIFillInTheBlank(AbstractQTIQuestion):

    title = u'Fill in the Blank'

    @property
    def answers(self):
        sols = self.context.solutions
        answers = []
        if not sols:
            return None
        for sol in sols:
            answers.append(sol.value)
        return answers

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/fill_in_the_blank', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        if self.answers:
            context['answers'] = self.answers
        return execute(renderer, {'context': context})


class QTIMatching(AbstractQTIQuestion):

    # TODO this is specific to an NTI ordering question, need to work out the other cases

    title = u'Matching'
    Label = namedtuple('Label', ['ident', 'mattext'])

    @property
    def labels(self):
        return [
            self.Label(u'label_' + unicode(i), x) for i, x in enumerate(self.context.labels)
        ]

    @property
    def values(self):
        values = []
        for i, value in enumerate(self.context.values):
            soup = BeautifulSoup(value)
            paragraphs = soup.find_all('p')
            content = '\n'.join([paragraph.text for paragraph in paragraphs])
            values.append(self.Label(u'value_' + unicode(i), content))
        return values

    @property
    def answers(self):
        sols = self.context.solutions
        answers = []
        num_qs = len(self.labels) or 1  # Avoid div by zero error
        q_value = 100.0/num_qs
        if not sols:
            # If there are no solutions we still need to return a placeholder dict to
            # iterate in the template.
            for _ in self.labels:
                answers.append({'value': q_value})
        else:
            if len(sols) > 1:
                logger.info(u'More than one solution')  # TODO handle
            for (label, value) in sols[0].value.items():
                answer = {'question': self.labels[int(label)].ident,
                          'solution': self.values[value].ident,
                          'value': q_value}
                answers.append(answer)
        return answers

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/matching', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        context['labels'] = self.labels
        context['values'] = self.values
        context['answers'] = self.answers
        return execute(renderer, {'context': context})


class QTIFileUpload(AbstractQTIQuestion):

    title = u'File Upload'

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/file_upload', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        return execute(renderer, {'context': context})


class QTIEssay(AbstractQTIQuestion):
    
    title = u'Essay'

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/essay', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        return execute(renderer, {'context': context})


class QTIFillInMultipleBlanks(AbstractQTIQuestion):

    title = u'Fill in Multiple Blanks'

    def __init__(self, context):
        super(QTIFillInMultipleBlanks, self).__init__(context)
        self.blanks = []

    @property
    def content(self):  # TODO need to get the dependencies out of these
        """
        This is canvas specific, replace all input fields with canvas's style of blank
        """
        # we want to use html.parser here so <html> and <body> tags aren't inserted
        question_content = BeautifulSoup(self.question.content, features='html.parser')
        entry_content = BeautifulSoup(self.context.content, features='html.parser')
        for blank in entry_content.find_all('input'):
            name = blank.attrs.get('name')
            blank.replace_with('[%s]' % name)
            self.blanks.append(name)
        question_content.append(entry_content)
        return question_content.prettify('utf-8')

    @property
    def answers(self):
        sols = self.context.solutions
        sol = sols[0]
        num_sols = len(sol.value) or 1  # Handle div by zero
        value = 100.0/num_sols
        answers = []
        if not sols:
            raise KeyError  # TODO we need a solution for these to template correctly
        for blank in self.blanks:
            key = 'response_%s' % blank
            reg_ex = sol.value[blank]
            answers.append({'blank_ident': key,
                            'mattext': blank,
                            'answer_ident': blank,
                            'answer': reg_ex.solution,
                            'value': value})
        return answers

    def to_xml(self, package=None):
        renderer = get_renderer('templates/parts/fill_in_multiple_blanks', '.pt', package)
        context = self.base_template_context
        context['mattext'] = self.content
        context['title'] = self.title
        context['answers'] = self.answers
        return execute(renderer, {'context': context})


class QTIMultipleDropdowns(AbstractQTIQuestion):
    pass
