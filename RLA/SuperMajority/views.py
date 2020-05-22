from audit.views import PluralityValidationView, PluralityRecountView, PluralityPreliminaryView


class PreliminaryView(PluralityPreliminaryView):
    template = 'SuperMajority/preliminary_view.html'


class RecountView(PluralityRecountView):
    recount_template = 'SuperMajority/recount_template.html'
    validate_url = '/supermajority/validated'

    def _transform_primary_count(self, audit, vote_count):
        candidates = list(audit.vote_count.keys())
        winner = candidates[0]
        grouped_count = {
            'Winner': vote_count[winner],
            'Losers': sum([vote_count[c] for c in vote_count if c != winner])
        }
        return grouped_count

    def _transform_primary_recount(self, audit, vote_recount):
        return self._transform_primary_count(audit, vote_recount)


class ValidationView(PluralityValidationView):
    recount_url = '/supermajority/recount'
