from decimal import Decimal

import pandas as pd
from cryptorandom.sample import random_sample
from django.http import Http404, HttpResponseServerError
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import TemplateView

from RLA import utils
from audit.forms import CreateAuditForm, RecountForm
from audit.models import Audit, RecountRegistry, SubAudit


class LandingPageView(TemplateView):
    template = 'audit/list_audits.html'

    def get(self, *args, **kwargs):
        audits = Audit.objects.all().order_by('-date')
        context = {'audits': audits}
        return render(self.request, self.template, context)


class CreateAuditView(TemplateView):
    template = 'audit/form_template.html'
    action = '/new/'

    @staticmethod
    def __create_subaudit(audit, W, L, vote_count, identifier):
        subaudit = SubAudit(
            identifier=identifier,
            audit=audit,
            vote_count=vote_count,
        )
        subaudit.T = {w: {l: Decimal(1.0) for l in L if w != l} for w in W}
        subaudit.Sw = {w: 1 for w in W}
        subaudit.Sl = {l: 1 for l in L}
        return subaudit

    @staticmethod
    def __create_plurality_audit(audit):
        df = pd.read_csv(audit.preliminary_count.path)
        vote_count = df.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()
        audit.vote_count = vote_count
        audit.accum_recount = {c: 0 for c in vote_count}
        audit.save()
        W = list(vote_count.keys())[:audit.n_winners]
        L = list(vote_count.keys())[audit.n_winners:]
        subaudit = CreateAuditView.__create_subaudit(audit, W, L, vote_count, utils.PRIMARY)
        subaudit.save()
        return redirect(f'/simplemajority/preliminary/{audit.pk}')

    @staticmethod
    def __create_super_majority_audit(audit):
        df = pd.read_csv(audit.preliminary_count.path)
        vote_count = df.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()
        audit.vote_count = vote_count
        audit.accum_recount = {c: 0 for c in vote_count}
        audit.n_winners = 1
        audit.save()
        subaudit = CreateAuditView.__create_subaudit(audit, ['Winner'], ['Losers'], vote_count, utils.PRIMARY)
        subaudit.save()
        return redirect(f'/supermajority/preliminary/{audit.pk}')

    @staticmethod
    def __create_dhondt_audit(audit):
        df = pd.read_csv(audit.preliminary_count.path)
        df['party'] = df['party'].fillna('')
        vote_count = df.groupby('party').sum()['votes'].sort_values(ascending=False).to_dict()
        audit.vote_count = vote_count
        audit.accum_recount = {p: 0 for p in vote_count}
        audit.save()
        pseudo_candidate_votes = {
            (p, i): utils.p(p, vote_count, i) for i in range(audit.n_winners) for p in vote_count.keys() if p
        }
        W, L = utils.dhondt_W_L_sets(pseudo_candidate_votes, audit.n_winners)
        Wp = []
        for winner, _ in W:
            if winner not in Wp:
                Wp.append(winner)

        Lp = []
        for loser, _ in L:
            if loser not in Lp:
                Lp.append(loser)

        primary_subaudit = CreateAuditView.__create_subaudit(audit, Wp, Lp, vote_count, utils.PRIMARY)
        for party in primary_subaudit.vote_count.keys():
            wp = list(filter(lambda x: x[0] == party, W))
            lp = list(filter(lambda x: x[0] == party, L))
            if wp:
                primary_subaudit.Sw[party] = max(wp, key=lambda x: x[1])[1] + 1

            if lp:
                primary_subaudit.Sl[party] = min(lp, key=lambda x: x[1])[1] + 1

        primary_subaudit.save()
        for party in Wp:
            party_df = df[df['party'] == party]
            party_count = party_df.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()
            candidates = list(party_count.keys())
            W = candidates[:primary_subaudit.Sw[party] - 1]
            L = candidates[primary_subaudit.Sw[party] - 1:]
            subaudit = CreateAuditView.__create_subaudit(audit, W, L, party_count, party)
            subaudit.save()

        return redirect(f'/dhondt/preliminary/{audit.pk}')

    def get(self, *args, **kwargs):
        form = CreateAuditForm()
        context = {
            'form': form,
            'action': self.action
        }
        return render(self.request, self.template, context)

    def post(self, *args, **kwargs):
        form = CreateAuditForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            audit = form.save()
            if form.cleaned_data['election_type'] == utils.SIMPLE_MAJORITY:
                return CreateAuditView.__create_plurality_audit(audit)

            elif form.cleaned_data['election_type'] == utils.SUPER_MAJORITY:
                return CreateAuditView.__create_super_majority_audit(audit)

            else:  # form.cleaned_data['election_type'] == utils.DHONDT:
                return CreateAuditView.__create_dhondt_audit(audit)

        context = {
            'form': form,
            'action': self.action
        }
        return render(self.request, self.template, context)


class AuditView(TemplateView):
    template = 'audit/view_audit.html'

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        try:
            audit = Audit.objects.get(pk=audit_pk)
            context = {'audit': audit}
            return render(self.request, self.template, context)

        except Audit.DoesNotExist:
            return Http404('Audit does not exist')


class PluralityPreliminaryView(TemplateView):
    template = ''

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        primary_subaudit = audit.subaudit_set.get(identifier=utils.PRIMARY)
        context = {
            'vote_count': primary_subaudit.vote_count,
            'audit_pk': audit_pk
        }
        return render(self.request, self.template, context)


class PluralityRecountView(TemplateView):
    recount_template = ''
    validate_url = ''

    @staticmethod
    def __init_shuffled(audit):
        seed = utils.get_random_seed(audit.random_seed_time)
        shuffled = []
        preliminary = pd.read_csv(audit.preliminary_count.path)
        table_count = preliminary.groupby('table').sum()['votes'].to_dict()
        for table in table_count:
            shuffled.extend(zip([table] * table_count[table], range(table_count[table])))

        primary_subaudit = audit.subaudit_set.get(identifier=utils.PRIMARY)
        shuffled = random_sample(
            shuffled,
            min(audit.max_polls, sum(primary_subaudit.vote_count.values())),
            method='Fisher-Yates',
            prng=int.from_bytes(seed, 'big')
        )
        audit.random_seed = seed
        audit.shuffled = shuffled
        audit.save()

    def _transform_primary_count(self, audit, vote_count):
        return vote_count

    def _transform_primary_recount(self, audit, vote_recount):
        return vote_recount

    def _transform_secondary_count(self, audit, vote_count):
        return vote_count

    def _transform_secondary_recount(self, audit, vote_recount):
        return vote_recount

    def _update_accum_recount(self, audit, recount):
        for c in recount:
            audit.accum_recount[c] += recount[c]

        audit.save()

    def _get_sample_size(self, audit):
        primary_subaudit = audit.subaudit_set.get(identifier=utils.PRIMARY)
        votes = list(primary_subaudit.vote_count.values())
        votes.sort(reverse=True)
        sample_size = utils.ASN(
            audit.risk_limit,
            votes[audit.n_winners - 1],
            votes[audit.n_winners],
            sum(primary_subaudit.vote_count.values())
        ) // 2
        sample_size = min(sample_size, len(audit.shuffled))
        return sample_size

    def _process_subaudit(self, audit, subaudit, vote_count, vote_recount):
        subaudit.T = utils.SPRT(vote_count, vote_recount, subaudit.T, audit.risk_limit, subaudit.Sw, subaudit.Sl)
        subaudit.max_p_value = utils.max_p_value(subaudit.T)
        subaudit.save()

    def _process_primary_subaudit(self, audit, subaudit, real_vote_recount):
        vote_count = self._transform_primary_count(audit, subaudit.vote_count)
        vote_recount = self._transform_primary_recount(audit, real_vote_recount)
        self._process_subaudit(audit, subaudit, vote_count, vote_recount)

    def _process_secondary_subaudit(self, audit, subaudit, real_vote_recount):
        vote_count = self._transform_secondary_count(audit, subaudit.vote_count)
        vote_recount = self._transform_secondary_recount(audit, real_vote_recount)
        self._process_subaudit(audit, subaudit, vote_count, vote_recount)

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        if audit.random_seed_time > timezone.now():
            return HttpResponseServerError('Random pulse has not yet been emitted')

        if not audit.random_seed:
            self.__init_shuffled(audit)

        sample_size = self._get_sample_size(audit)
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

            real_recount = pd.read_csv(recount_registry.recount.path)
            real_vote_recount = real_recount.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()
            if 'party' in real_recount.columns:
                real_recount['party'] = real_recount['party'].fillna('')

            subaudit_set = audit.subaudit_set.all()
            recounted_ballots = form.cleaned_data['recounted_ballots']

            audit.shuffled = audit.shuffled[recounted_ballots:]
            audit.polled_ballots += recounted_ballots
            self._update_accum_recount(audit, real_vote_recount)
            audit.save()

            # Primary subaudit
            primary_subaudit = subaudit_set.get(identifier=utils.PRIMARY)
            self._process_primary_subaudit(audit, primary_subaudit, real_vote_recount)

            # Secondary subaudits
            for subaudit in subaudit_set.exclude(identifier=utils.PRIMARY):
                self._process_secondary_subaudit(audit, subaudit, real_vote_recount)

            return redirect(f'{self.validate_url}/{audit_pk}/')

        sample_size = self._get_sample_size(audit)
        tables = utils.get_sample(audit, sample_size)
        context = {
            'form': form,
            'tables': tables,
            'sample_size': sample_size,
            'audit_pk': audit_pk
        }
        return render(self.request, self.recount_template, context)


class PluralityValidationView(TemplateView):
    template = 'audit/validate_template.html'
    recount_url = ''

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)

        max_p_value = 0
        is_validated = True
        for subaudit in audit.subaudit_set.all():
            max_p_value = max(max_p_value, subaudit.max_p_value)
            is_validated = is_validated and utils.validated(subaudit.T, audit.risk_limit)

        if is_validated:
            audit.in_progress = False
            audit.validated = True

        elif audit.max_polls <= audit.polled_ballots:
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
            'ballot_cap': audit.max_polls,
            'is_validated': is_validated,
            'max_p_value': max_p_value,
            'recount_url': f'{self.recount_url}/{audit_pk}/'
        }
        return render(self.request, self.template, context)
