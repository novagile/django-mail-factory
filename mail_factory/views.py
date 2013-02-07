# -*- coding: utf-8 -*-
from django.shortcuts import redirect
from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView, FormView
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils import translation

from mail_factory import factory

admin_required = user_passes_test(lambda x: x.is_superuser)


class MailListView(TemplateView):
    """Return a list of mails."""
    template_name = 'mail_factory/list.html'

    def get_context_data(self, **kwargs):
        """Return object_list."""
        data = super(MailListView, self).get_context_data(**kwargs)
        mail_list = []

        for mail_name, mail_class in sorted(factory.mail_map.items(),
                                            key=lambda x: x[0]):
            mail_list.append((mail_name, mail_class.__name__))
        data['mail_map'] = mail_list
        return data


class MailDetailView(TemplateView):
    """Return a detail of a mail."""
    template_name = 'mail_factory/detail.html'

    def dispatch(self, request, mail_name, mimetype=None, lang=None):
        if mimetype is None:
            mimetype = 'txt'

        self.mimetype = mimetype
        self.mail_name = mail_name
        self.lang = lang

        if self.mail_name not in factory.mail_map:
            raise Http404

        return super(MailDetailView, self).dispatch(request)

    def render_to_response(self, context, **response_kwargs):
        if self.mimetype != 'html' or not 'body_html' in context:
            return super(MailDetailView, self).render_to_response(context, **response_kwargs)

        return HttpResponse(context['body_html'])

    def get_context_data(self, **kwargs):
        data = super(MailDetailView, self).get_context_data(**kwargs)

        data['mail_name'] = self.mail_name

        mail = factory.get_mail_object(self.mail_name, {
            'user': self.request.user
        })
        mail.lang = self.lang

        data['mail'] = mail

        msg = mail.create_email_msg([settings.SERVER_EMAIL, ])

        data['msg'] = msg

        alternatives = dict((mimetype, content)
                            for content, mimetype in data['msg'].alternatives)

        data['alternatives'] = alternatives

        if 'text/html' in alternatives:
            data['body_html'] = alternatives['text/html']

        return data


class MailFormView(FormView):
    template_name = 'mail_factory/form.html'

    def dispatch(self, request, mail_name):
        self.mail_name = mail_name
        if self.mail_name not in factory.mail_map:
            raise Http404

        self.raw = 'raw' in request.POST
        self.send = 'send' in request.POST
        self.email = request.POST.get('email')

        return super(MailFormView, self).dispatch(request)

    def get_form_class(self):
        return factory._get_mail_form(self.mail_name)

    def form_valid(self, form):
        if self.raw:
            return HttpResponse('<pre>%s</pre>' %
                                factory.get_raw_content(
                                    self.mail_name,
                                    [settings.DEFAULT_FROM_EMAIL],
                                    form.cleaned_data).message())

        if self.send:
            factory.mail(self.mail_name, [self.email], form.cleaned_data)
            messages.success(self.request,
                             '%s mail sent to %s' % (self.mail_name,
                                                     self.email))
            return redirect('mail_factory_list')

        return HttpResponse(
            factory.get_html_for(self.mail_name, form.cleaned_data))

    def get_context_data(self, **kwargs):
        data = super(MailFormView, self).get_context_data(**kwargs)

        data['mail_name'] = self.mail_name
        data['languages'] = settings.LANGUAGES
        data['lang'] = translation.get_language()

        try:
            data['admin_email'] = settings.ADMINS[0][1]
        except IndexError:
            data['admin_email'] = getattr(
                settings, 'SUPPORT_EMAIL',
                getattr(settings, 'DEFAULT_FROM_EMAIL', ''))

        return data


mail_list = admin_required(MailListView.as_view())
form = admin_required(MailFormView.as_view())
detail = admin_required(MailDetailView.as_view())
