from django import forms

from audit.models import BRAVOAudit, DHONDTAudit, Audit


class AuditForm(forms.ModelForm):
    risk_limit = forms.FloatField(min_value=0.0, max_value=1.0)
    max_polls = forms.IntegerField(min_value=1)

    class Meta:
        model = Audit
        fields = ['risk_limit', 'random_seed_time', 'max_polls']


class BRAVOAuditForm(AuditForm):
    class Meta:
        model = BRAVOAudit
        fields = AuditForm.Meta.fields + ['winners']


class DHONDTAuditForm(AuditForm):
    class Meta:
        model = DHONDTAudit
        fields = AuditForm.Meta.fields + ['seats']

