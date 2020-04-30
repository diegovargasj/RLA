from django import forms

from audit.models import BRAVOAudit, Audit


class ListElectionTypesForm(forms.Form):
    choices = (
        ('simplemajority', 'Simple Majority'),
        ('supermajority', 'Super Majority'),
        ('dhondt', 'D\'Hondt')
    )
    types = forms.ChoiceField(
        choices=choices,
        label='Election Type',
        required=True
    )


class CreateAuditForm(forms.Form):
    election_types = (
        ('simplemajority', 'Simple Majority'),
        ('supermajority', 'Super Majority'),
        ('dhondt', 'D\'Hondt')
    )
    audit_types = (
        ('ballotpolling', 'Ballot Polling'),
        ('comparison', 'Comparison')
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
            preliminary_count=self.cleaned_data['preliminary_count_file']
        )
        audit.save()
        return audit


class AuditForm(forms.Form):
    risk_limit = forms.FloatField(min_value=0.0, max_value=1.0)
    random_seed_time = forms.DateTimeField()
    max_polls = forms.IntegerField(min_value=1)


class BRAVOAuditForm(forms.ModelForm):
    class Meta:
        model = BRAVOAudit
        fields = ['winners']
