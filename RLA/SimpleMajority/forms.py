from django import forms

import pandas as pd


class RecountForm(forms.Form):
    recount = forms.FileField()
    recounted_ballots = forms.IntegerField(widget=forms.HiddenInput())

    def is_valid(self):
        valid = super().is_valid()
        df = pd.read_csv(self.cleaned_data['recount'])
        if not set(df.columns) <= {'table', 'candidate', 'votes'}:
            valid = False
            self.add_error('recount', 'Headers not valid')

        if 'votes' in df.columns and df['votes'].sum() != self.cleaned_data['recounted_ballots']:
            valid = False
            self.add_error('recount', 'Incorrect number of recounted ballots')

        return valid
