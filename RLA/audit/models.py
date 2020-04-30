from django.db import models

# Create your models here.
from picklefield import PickledObjectField


class Audit(models.Model):
    date = models.DateTimeField(auto_now=True)
    in_progress = models.BooleanField(default=True)
    election_type = models.CharField(max_length=16, default='')
    risk_limit = models.FloatField()
    random_seed = models.BinaryField(blank=True, null=True)
    random_seed_time = models.DateTimeField()
    n_winners = models.IntegerField(default=1)
    max_polls = models.IntegerField()
    preliminary_count = models.FileField()
    recount = models.FileField(blank=True, null=True)
    shuffled = PickledObjectField(default=list)


class SubAudit(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    ballots_polled = models.IntegerField(default=0)
    T = PickledObjectField(default=dict)


class PseudiCandidate(models.Model):
    name = models.CharField(max_length=128)


class BRAVOAudit(SubAudit):
    winners = models.IntegerField()


class Candidate(PseudiCandidate):
    subaudit = models.ForeignKey(BRAVOAudit, on_delete=models.PROTECT)


class RecountRegistry(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)
    recount = models.FileField()
    timestamp = models.DateTimeField(auto_now=True)
