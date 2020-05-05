from collections import Counter
from decimal import getcontext, Decimal

import pandas as pd
from cryptorandom.sample import random_sample
from django.http import Http404, HttpResponseServerError
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import TemplateView

from RLA import utils
from audit.forms import CreateAuditForm, RecountForm
from audit.models import Audit, BRAVOAudit, RecountRegistry


def landing_page_view(request):
    audits = Audit.objects.all().order_by('-date')
    context = {'audits': audits}
    return render(request, 'audit/list_audits.html', context)


def create_audit_view(request):
    form = CreateAuditForm()
    if request.method == 'POST':
        form = CreateAuditForm(request.POST, request.FILES)
        if form.is_valid():
            audit = form.save()
            if form.cleaned_data['election_type'] == 'simplemajority':
                subaudit = BRAVOAudit(
                    audit=audit,
                    winners=form.cleaned_data['n_winners']
                )
                candidates = list(audit.vote_count.keys())
                W = candidates[:audit.n_winners]
                L = candidates[audit.n_winners:]
                subaudit.T = {w: {l: Decimal(1.0) for l in L} for w in W}
                subaudit.save()
                return redirect(f'/simplemajority/preliminary/{audit.pk}')

            elif form.cleaned_data['election_type'] == 'supermajority':
                subaudit = BRAVOAudit(
                    audit=audit,
                    winners=1
                )
                candidates = ['Winner', 'Losers']
                subaudit.T = {candidates[0]: {candidates[1]: Decimal(1)}}
                subaudit.save()
                return redirect(f'/supermajority/preliminary/{audit.pk}')

            else:  # form.cleaned_data['election_type'] == 'dhondt':
                # audit = create_dhondt_audit_view(form)
                return Http404('Not implemented yet')

    context = {
        'form': form,
        'action': '/new/'
    }
    return render(request, 'audit/form_template.html', context)


def view_audit_view(request, audit_pk):
    audit = Audit.objects.get(pk=audit_pk)
    context = {'audit': audit}
    return render(request, 'audit/view_audit.html', context)


class PluralityPreliminaryView(TemplateView):
    template = ''

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        context = {
            'vote_count': audit.vote_count,
            'audit_pk': audit_pk
        }
        return render(self.request, self.template, context)


class PluralityRecountView(TemplateView):
    recount_template = ''
    validate_url = ''

    @staticmethod
    def __init_shuffled(audit):
        seed = utils.get_random_seed(audit.random_seed_time)
        audit.random_seed = seed
        shuffled = []
        preliminary = pd.read_csv(audit.preliminary_count)
        table_count = preliminary.groupby('table').sum()['votes'].to_dict()
        for table in table_count:
            shuffled.extend(zip([table] * table_count[table], range(table_count[table])))

        shuffled = random_sample(
            shuffled,
            len(shuffled),
            method='Fisher-Yates',
            prng=int.from_bytes(seed, 'big')
        )
        audit.shuffled = shuffled
        audit.save()

    def _transform_vote_count(self, audit, vote_count):
        return vote_count

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        if audit.random_seed_time > timezone.now():
            return HttpResponseServerError('Random pulse has not yet been emitted')

        if not audit.random_seed:
            self.__init_shuffled(audit)

        votes = list(audit.vote_count.values())
        votes.sort(reverse=True)
        sample_size = utils.ASN(
            audit.risk_limit,
            votes[audit.n_winners - 1],
            votes[audit.n_winners],
            sum(audit.vote_count.values())
        ) // 2
        form = RecountForm(initial={'recounted_ballots': sample_size})

        tables = utils.get_sample(audit, sample_size)
        context = {
            'form': form,
            'tables': tables,
            'sample_size': sample_size,
            'audit_pk': audit_pk
        }
        return render(self.request, self.recount_template, context)

    def post(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        if audit.random_seed_time > timezone.now():
            return HttpResponseServerError('Random pulse has not yet been emitted')

        form = RecountForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            recount_registry = RecountRegistry(
                audit=audit,
                recount=form.cleaned_data['recount']
            )
            recount_registry.save()
            subaudit = audit.subaudit_set.first()
            real_recount = pd.read_csv(recount_registry.recount)
            real_vote_recount = real_recount.groupby('candidate').sum()['votes'].to_dict()

            audit.shuffled = audit.shuffled[form.cleaned_data['recounted_ballots']:]
            audit.accum_recount = dict(Counter(audit.accum_recount) + Counter(real_vote_recount))
            audit.save()

            vote_count = self._transform_vote_count(audit, audit.vote_count)
            vote_recount = self._transform_vote_count(audit, real_vote_recount)

            subaudit.T = utils.SPRT(vote_count, vote_recount, subaudit.T, audit.risk_limit)
            subaudit.save()
            return redirect(f'{self.validate_url}/{audit_pk}/')


class PluralityValidationView(TemplateView):
    template = 'audit/validate_template.html'
    recount_url = ''

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        subaudit = audit.subaudit_set.first()
        is_validated = utils.validated(subaudit.T, audit.risk_limit)
        max_p_value = utils.max_p_value(subaudit)
        if is_validated:
            audit.in_progress = False
            audit.save()

        votes = {}
        for c in audit.vote_count:
            votes[c] = {
                'preliminary': audit.vote_count[c],
                'recount': audit.accum_recount[c]
            }

        context = {
            'votes': votes,
            'total_count': sum(audit.vote_count.values()),
            'total_recount': sum(audit.accum_recount.values()),
            'is_validated': is_validated,
            'max_p_value': max_p_value,
            'recount_url': f'{self.recount_url}/{audit_pk}/'
        }
        return render(self.request, self.template, context)
