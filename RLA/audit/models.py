from django.db import models

from picklefield import PickledObjectField


class Audit(models.Model):
    date = models.DateTimeField(auto_now=True)
    in_progress = models.BooleanField(default=True)
    validated = models.BooleanField(default=False)
    election_type = models.CharField(max_length=16, default='')
    risk_limit = models.FloatField()
    random_seed = models.BinaryField(blank=True, null=True)
    random_seed_time = models.DateTimeField()
    n_winners = models.IntegerField(default=1)
    max_polls = models.IntegerField()
    polled_ballots = models.IntegerField(default=0)
    preliminary_count = models.FileField()
    shuffled = PickledObjectField(default=list)
    vote_count = PickledObjectField(default=dict)
    accum_recount = PickledObjectField(default=dict)


class SubAudit(models.Model):
    identifier = models.CharField(max_length=16)
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    Sw = PickledObjectField(default=dict)
    Sl = PickledObjectField(default=dict)
    T = PickledObjectField(default=dict)
    max_p_value = models.FloatField(default=0)
    vote_count = PickledObjectField(default=dict)

    class Meta:
        unique_together = ['identifier', 'audit']


class PseudiCandidate(models.Model):
    name = models.CharField(max_length=128)


class RecountRegistry(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    recount = models.FileField()
    timestamp = models.DateTimeField(auto_now=True)
