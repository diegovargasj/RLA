from audit.views import PluralityValidationView, PluralityRecountView, PluralityPreliminaryView


class PreliminaryView(PluralityPreliminaryView):
    template = 'SimpleMajority/preliminary_view.html'


class RecountView(PluralityRecountView):
    recount_template = 'SimpleMajority/recount_template.html'
    validate_url = '/simplemajority/validated'


class ValidationView(PluralityValidationView):
    recount_url = '/simplemajority/recount'
