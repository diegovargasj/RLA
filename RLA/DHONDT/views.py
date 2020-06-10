import pandas as pd

from RLA import utils
from audit.views import PluralityPreliminaryView, PluralityRecountView, PluralityValidationView


class PreliminaryView(PluralityPreliminaryView):
    template = 'DHONDT/preliminary_view.html'


class RecountView(PluralityRecountView):
    recount_template = 'DHONDT/recount_template.html'
    validate_url = '/dhondt/validated'

    def _update_accum_recount(self, audit, recount):
        df = pd.read_csv(audit.preliminary_count.path)
        df['party'] = df['party'].fillna('')
        parties = df.groupby('candidate')['party'].first().to_dict()
        for c in recount:
            party = parties[c]
            audit.accum_recount[party] += recount[c]

        audit.save()

    def _get_sample_size(self, audit):
        primary_subaudit = audit.subaudit_set.get(identifier=utils.PRIMARY)
        N = sum(primary_subaudit.vote_count.values())
        sample_size = utils.dhondt_sample_size(
            N,
            audit.risk_limit / primary_subaudit.max_p_value,
            primary_subaudit.vote_count,
            primary_subaudit.Sw,
            primary_subaudit.Sl
        )
        for subaudit in audit.subaudit_set.exclude(identifier=utils.PRIMARY):
            if not subaudit.validated():
                sample_size = max(
                    sample_size,
                    utils.ASN(
                        audit.risk_limit / subaudit.max_p_value,
                        subaudit.vote_count,
                        subaudit.Sw,
                        subaudit.Sl
                    )
                )

        return min(sample_size, len(audit.shuffled)) * len(primary_subaudit.vote_count.keys())

    def _transform_primary_recount(self, audit, vote_recount):
        df = pd.read_csv(audit.preliminary_count.path)
        df['party'] = df['party'].fillna('')
        party_per_candidate = df.groupby('candidate')['party'].first().to_dict()

        transformed_recount = {}
        for candidate in party_per_candidate:
            if party_per_candidate[candidate] not in transformed_recount:
                transformed_recount[party_per_candidate[candidate]] = 0

            transformed_recount[party_per_candidate[candidate]] += vote_recount[candidate]

        return transformed_recount

    def _comparison_table_transform(self, audit, vote_count):
        return self._transform_primary_recount(audit, vote_count)

    def _get_party_seat_pairs(self, audit):
        members_per_party = {}
        preliminary = pd.read_csv(audit.preliminary_count.path)
        parties = list(preliminary['party'].unique())
        for party in parties:
            p = preliminary[preliminary['party'] == party]
            candidates = p.sort_values('votes', ascending=False)['candidate'].unique()
            members_per_party[party] = list(candidates)

        pseudo_candidate_votes = {
            (p, i): utils.p(p, audit.vote_count, i) for p in parties if p
            for i in range(min(audit.n_winners, len(members_per_party[p])))
        }
        return utils.dhondt_W_L_sets(pseudo_candidate_votes, audit.n_winners)


class ValidationView(PluralityValidationView):
    template = 'DHONDT/validate_template.html'
    recount_url = '/dhondt/recount'
