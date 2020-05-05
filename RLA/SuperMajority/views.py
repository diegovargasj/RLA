from audit.views import PluralityValidationView, PluralityRecountView, PluralityPreliminaryView


def _count_to_grouped_count(vote_count, winner):
    grouped_count = {'Winner': 0, 'Losers': 0}
    for c in vote_count:
        if c == winner:
            grouped_count['Winner'] += vote_count[c]

        else:
            grouped_count['Losers'] += vote_count[c]

    return grouped_count


class PreliminaryView(PluralityPreliminaryView):
    template = 'SuperMajority/preliminary_view.html'


class RecountView(PluralityRecountView):
    recount_template = 'SuperMajority/recount_template.html'
    validate_url = '/supermajority/validated'

    def _transform_vote_count(self, audit, vote_count):
        candidates = list(audit.vote_count.keys())
        W = candidates[0]
        return _count_to_grouped_count(vote_count, W)


class ValidationView(PluralityValidationView):
    recount_url = '/supermajority/recount'
