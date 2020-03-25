from django.db import models

# Create your models here.
from picklefield import PickledObjectField


class Audit(models.Model):
    risk_limit = models.FloatField()
    random_seed = models.BinaryField(blank=True, null=True)
    random_seed_time = models.DateTimeField()
    max_polls = models.IntegerField()
    ballots_polled = models.IntegerField(default=0)
    T = PickledObjectField(default={})


class PseudiCandidate(models.Model):
    name = models.CharField()
    number = models.IntegerField()

    class Meta:
        unique_together = ("name", "audit")


class BRAVOAudit(Audit):
    winners = models.IntegerField()


class DHONDTAudit(Audit):
    seats = models.IntegerField()


class Candidate(PseudiCandidate):
    audit = models.ForeignKey(BRAVOAudit, on_delete=models.PROTECT)


class Party(PseudiCandidate):
    audit = models.ForeignKey(DHONDTAudit, on_delete=models.PROTECT)


class PartyMember(PseudiCandidate):
    party = models.ForeignKey(Party, on_delete=models.PROTECT)


class Table(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)


class TableRegistry(models.Model):
    table_number = models.IntegerField()
    candidate = models.ForeignKey(Table, on_delete=models.PROTECT)
    preliminary_votes = models.IntegerField(default=0)
    audited_votes = models.IntegerField(default=0)

    class Meta:
        unique_together = ("table_number", "candidate")
