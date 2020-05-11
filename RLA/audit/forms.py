import pandas as pd
from django import forms

from audit.models import Audit
from RLA import utils


class ListElectionTypesForm(forms.Form):
    choices = (
        (utils.SIMPLE_MAJORITY, 'Simple Majority'),
        (utils.SUPER_MAJORITY, 'Super Majority'),
        (utils.DHONDT, 'D\'Hondt')
    )
    types = forms.ChoiceField(
        choices=choices,
        label='Election Type',
        required=True
    )


class CreateAuditForm(forms.Form):
    election_types = (
        (utils.SIMPLE_MAJORITY, 'Simple Majority'),
        (utils.SUPER_MAJORITY, 'Super Majority'),
        (utils.DHONDT, 'D\'Hondt')
    )
    audit_types = (
        (utils.BALLOT_POLLING, 'Ballot Polling'),
        (utils.COMPARISON, 'Comparison')
    )
    election_type = forms.ChoiceField(
        choices=election_types,
        label='Election Type',
        required=True
    )
    audit_type = forms.ChoiceField(
        choices=audit_types,
        label='Audit Type',
        required=True
    )
    random_seed_time = forms.DateTimeField(
        label='Random Seed Time',
        required=True
    )
    risk_limit = forms.FloatField(
        min_value=0.0,
        max_value=1.0,
        label='Risk Limit',
        required=True
    )
    n_winners = forms.IntegerField(
        min_value=1,
        label='Number of Winners',
        required=True
    )
    max_polls = forms.IntegerField(
        min_value=1,
        label='Maximum Pool Count',
        required=True
    )
    preliminary_count_file = forms.FileField(
        label='Preliminary Count File',
        required=True
    )

    def save(self):
        audit = Audit.objects.create(
            election_type=self.cleaned_data['election_type'],
            random_seed_time=self.cleaned_data['random_seed_time'],
            risk_limit=self.cleaned_data['risk_limit'],
            n_winners=self.cleaned_data['n_winners'],
            max_polls=self.cleaned_data['max_polls'],
            preliminary_count=self.cleaned_data['preliminary_count_file'],
        )
        audit.save()
        return audit


class AuditForm(forms.Form):
    risk_limit = forms.FloatField(min_value=0.0, max_value=1.0)
    random_seed_time = forms.DateTimeField()
    max_polls = forms.IntegerField(min_value=1)


class RecountForm(forms.Form):
    recount = forms.FileField()
    recounted_ballots = forms.IntegerField(widget=forms.HiddenInput())

    def is_valid(self):
        valid = super().is_valid()
        df = pd.read_csv(self.cleaned_data['recount'])
        if not set(df.columns) >= {'table', 'candidate', 'votes'}:
            valid = False
            self.add_error('recount', 'Headers not valid')

        if 'votes' in df.columns and df['votes'].sum() != self.cleaned_data['recounted_ballots']:
            valid = False
            self.add_error('recount', 'Incorrect number of recounted ballots')

        return valid
