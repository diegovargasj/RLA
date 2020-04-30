from django import forms

from DHONDT.models import DHONDTAudit, Party, PartyMember
from audit.forms import AuditForm
from audit.models import Audit


class DHONDTAuditForm(forms.ModelForm):
    class Meta:
        model = DHONDTAudit
        fields = ['seats']


class CreateDHONDTForm(AuditForm):
    # Dynamic forms https://www.caktusgroup.com/blog/2018/05/07/creating-dynamic-forms-django/
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['party_0'] = forms.CharField()
        self.fields['party_0_member_0'] = forms.CharField()
        self.fields['party_1'] = forms.CharField()
        self.fields['party_1_member_0'] = forms.CharField()

    def clean(self):
        parties = dict()
        party_index = 0
        party_field = 'party_0'
        while self.cleaned_data.get(party_field):
            party = self.cleaned_data[party_field]
            if party in parties:
                self.add_error(party_field, 'Duplicate')

            elif party:
                parties[party] = []
                member_index = 0
                member_field = f'{party_field}_member_{member_index}'
                while self.cleaned_data.get(member_field):
                    member = self.cleaned_data[member_field]
                    if member in parties[party]:
                        self.add_error(member_field, 'Duplicate')

                    elif member:
                        parties[party].append(member)

                    member_index += 1
                    member_field = f'{party_field}_member_{member_index}'

            party_index += 1
            party_field = f'party_{party_index}'

        self.cleaned_data['parties'] = parties

    def save(self, commit=True):
        audit = Audit.objects.create(
            election_type="D'Hondt",
            risk_limit=self.cleaned_data['risk_limit'],
            random_seed_time=self.cleaned_data['random_seed_time'],
            max_polls=self.cleaned_data['max_polls']
        )
        # TODO create sub audits, parties and party members
        if commit:
            audit.save()

        return audit


class PreliminaryDHONDTForm(forms.Form):
    pass


class RecountDHONDTForm(forms.Form):
    pass
