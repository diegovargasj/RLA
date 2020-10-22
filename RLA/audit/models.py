import pandas as pd
from django.db import models
from picklefield import PickledObjectField

from RLA import utils


class Audit(models.Model):
    date = models.DateTimeField(auto_now=True)
    in_progress = models.BooleanField(default=True)
    validated = models.BooleanField(default=False)
    election_type = models.CharField(max_length=16)
    audit_type = models.CharField(max_length=16)
    risk_limit = models.FloatField()
    random_seed = models.CharField(max_length=128, blank=True, null=True)
    random_seed_time = models.DateTimeField()
    n_winners = models.IntegerField(default=1)
    max_polls = models.IntegerField()
    polled_ballots = models.IntegerField(default=0)
    preliminary_count = models.FileField()
    shuffled = PickledObjectField(default=list)
    vote_count = PickledObjectField(default=dict)
    accum_recount = PickledObjectField(default=dict)
    max_p_value = models.FloatField(default=1)

    def _update_accum_recounted(self, recount, save=True):
        for c in recount:
            self.accum_recount[c] += recount[c]

        if save:
            self.save()

    def get_df(self, path):
        df = pd.read_csv(path)
        if self.election_type == utils.DHONDT:
            df['party'] = df['party'].fillna('')

        return df

    def get_grouped(self, df):
        if self.election_type == utils.DHONDT:
            group = df.groupby('party')

        else:  # self.election_type == utils.SIMPLE_MAJORITY or self.election_type == utils.SUPER_MAJORITY
            group = df.groupby('candidate')

        return group.sum()['votes'].sort_values(ascending=False).to_dict()

    def add_polled_ballots(self, recount_df, save=True):
        vote_recount = self.get_grouped(recount_df)
        self._update_accum_recounted(vote_recount, save=False)
        self.polled_ballots += sum(vote_recount.values())

        if self.audit_type == utils.BALLOT_POLLING:
            self.shuffled = self.shuffled[sum(vote_recount.values()):]

        else:  # self.audit_type == utils.COMPARISON
            table_count = len(recount_df['table'].unique())
            self.shuffled = self.shuffled[table_count:]

        if save:
            self.save()


class SubAudit(models.Model):
    identifier = models.CharField(max_length=16)
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    Sw = PickledObjectField()
    Sl = PickledObjectField()
    T = PickledObjectField()
    max_p_value = models.FloatField(default=1)
    vote_count = PickledObjectField()

    class Meta:
        unique_together = ['identifier', 'audit']

    def validated(self):
        if self.audit.audit_type == utils.BALLOT_POLLING:
            return utils.validated(self.T, self.audit.risk_limit)

        else:  # self.audit.audit_type == utils.COMPARISON
            return self.T >= 1 / self.audit.risk_limit

    def get_W_L(self):
        W = [p for p in self.Sw]
        L = [p for p in self.Sl if p not in W]
        return W, L


class RecountRegistry(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    recount = models.FileField()
    timestamp = models.DateTimeField(auto_now=True)
