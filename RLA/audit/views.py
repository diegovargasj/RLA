import math
from decimal import Decimal

import pandas as pd
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
        if audit.audit_type == utils.BALLOT_POLLING:
            subaudit.T = {w: {l: Decimal(1.0) for l in L if w != l} for w in W}

        else:  # audit.audit_type == utils.COMPARISON
            subaudit.T = 1.0

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
            context = {
                'audit': audit,
                'votes': {
                    c: {
                        'preliminary': audit.vote_count[c],
                        'recount': audit.accum_recount[c]
                    } for c in audit.vote_count
                },
                'total_count': sum(audit.vote_count.values()),
                'total_recount': sum(audit.accum_recount.values())
            }
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

    def _transform_primary_count(self, audit, vote_count):
        return vote_count

    def _transform_primary_recount(self, audit, vote_recount):
        return vote_recount

    def _transform_secondary_count(self, audit, vote_count):
        return vote_count

    def _transform_secondary_recount(self, audit, vote_recount):
        return vote_recount

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

    def _samplesize2tables(self, audit, sample_size):
        df = pd.read_csv(audit.preliminary_count.path)
        mean_ballots_per_table = df.groupby('table').sum()['votes'].mean()
        return math.ceil(sample_size / mean_ballots_per_table)

    def _process_ballot_polling_subaudit(self, audit, subaudit, vote_count, vote_recount):
        subaudit.T = utils.ballot_polling_SPRT(vote_count, vote_recount, subaudit.T, audit.risk_limit, subaudit.Sw, subaudit.Sl)
        subaudit.max_p_value = utils.max_p_value(subaudit.T)
        subaudit.save()
        audit.max_p_value = max(audit.max_p_value, subaudit.max_p_value)
        audit.save()

    def _process_comparison_subaudit(self, audit, subaudit, table_count, table_recount, W, L, um, U):
        subaudit.T *= utils.comparison_SPRT(
            subaudit.vote_count,
            table_count,
            table_recount,
            W,
            L,
            um,
            U
        )
        subaudit.save()

    def _process_primary_subaudit(self, audit, subaudit, real_vote_recount):
        vote_count = self._transform_primary_count(audit, subaudit.vote_count)
        vote_recount = self._transform_primary_recount(audit, real_vote_recount)
        self._process_ballot_polling_subaudit(audit, subaudit, vote_count, vote_recount)

    def _process_secondary_subaudit(self, audit, subaudit, real_vote_recount):
        vote_count = self._transform_secondary_count(audit, subaudit.vote_count)
        vote_recount = self._transform_secondary_recount(audit, real_vote_recount)
        self._process_ballot_polling_subaudit(audit, subaudit, vote_count, vote_recount)

    def _ballot_polling_recount(self, audit, real_recount):
        real_vote_recount = real_recount.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()
        subaudit_set = audit.subaudit_set.all()

        # Primary subaudit
        primary_subaudit = subaudit_set.get(identifier=utils.PRIMARY)
        self._process_primary_subaudit(audit, primary_subaudit, real_vote_recount)

        # Secondary subaudits
        for subaudit in subaudit_set.exclude(identifier=utils.PRIMARY):
            self._process_secondary_subaudit(audit, subaudit, real_vote_recount)

    def _comparison_recount(self, audit, real_recount):
        subaudit_set = audit.subaudit_set.all()

        primary_subaudit = subaudit_set.get(identifier=utils.PRIMARY)
        df = pd.read_csv(audit.preliminary_count.path)
        Wp, Lp = primary_subaudit.get_W_L()
        u = utils.upper_bound(primary_subaudit.vote_count, Wp, Lp, primary_subaudit.Sw, primary_subaudit.Sl)
        V = max(df.groupby('table').sum()['votes'])
        um = u * V
        U = um * len(df['table'].unique())
        # TODO change this for D'Hondt elections
        W = [(c, 0) for c in Wp]
        L = [(c, 0) for c in Lp]
        for table in list(real_recount['table'].unique()):
            reported_table = df[df['table'] == table]
            table_count = reported_table.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()

            table_df = real_recount[real_recount['table'] == table]
            table_recount = table_df.groupby('candidate').sum()['votes'].sort_values(ascending=False).to_dict()

            primary_vote_count = self._transform_primary_count(audit, table_count)
            primary_vote_recount = self._transform_primary_recount(audit, table_recount)

            self._process_comparison_subaudit(audit, primary_subaudit, primary_vote_count, primary_vote_recount, W, L, um, U)

            secondary_vote_count = self._transform_secondary_count(audit, table_count)
            secondary_vote_recount = self._transform_secondary_recount(audit, table_recount)
            for subaudit in subaudit_set.exclude(identifier=utils.PRIMARY):
                self._process_comparison_subaudit(audit, subaudit, secondary_vote_count, secondary_vote_recount, W, L, um, U)

        primary_subaudit.max_p_value = 1 / primary_subaudit.T
        primary_subaudit.save()
        max_p_value = primary_subaudit.max_p_value
        for subaudit in subaudit_set.exclude(identifier=utils.PRIMARY):
            subaudit.max_p_value = 1 / subaudit.T
            subaudit.save()
            max_p_value = max(max_p_value, subaudit.max_p_value)

        audit.max_p_value = max_p_value
        audit.save()

    def get(self, *args, **kwargs):
        audit_pk = kwargs.get('audit_pk')
        audit = Audit.objects.get(pk=audit_pk)
        if audit.random_seed_time > timezone.now():
            return HttpResponseServerError('Random pulse has not yet been emitted')

        if not audit.random_seed:
            audit.init_shuffled()

        sample_size = self._get_sample_size(audit)
        draw_size = sample_size
        if audit.audit_type == utils.COMPARISON:
            draw_size = self._samplesize2tables(audit, sample_size)

        form = RecountForm(initial={'recounted_ballots': sample_size})

        tables = utils.get_sample(audit, draw_size)
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

            real_recount = audit.get_df(recount_registry.recount.path)

            audit.add_polled_ballots(real_recount, save=False)
            audit.max_p_value = 0
            audit.save()

            if audit.audit_type == utils.BALLOT_POLLING:
                self._ballot_polling_recount(audit, real_recount)

            else:  # audit.audit_type == utils.COMPARISON
                self._comparison_recount(audit, real_recount)

            return redirect(f'{self.validate_url}/{audit_pk}/')

        sample_size = self._get_sample_size(audit)
        draw_size = sample_size
        if audit.audit_type == utils.COMPARISON:
            draw_size = self._samplesize2tables(audit, sample_size)

        tables = utils.get_sample(audit, draw_size)
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

        validated = all([subaudit.validated() for subaudit in audit.subaudit_set.all()])
        if validated:
            audit.validated = True

        if audit.validated or audit.max_polls <= audit.polled_ballots:
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
            'total_recount': audit.polled_ballots,
            'ballot_cap': audit.max_polls,
            'is_validated': audit.validated,
            'max_p_value': audit.max_p_value,
            'recount_url': f'{self.recount_url}/{audit_pk}/'
        }
        return render(self.request, self.template, context)
