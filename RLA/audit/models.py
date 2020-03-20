from django.db import models

# Create your models here.


class Audit(models.Model):
    audit_type = models.CharField()
    risk_limit = models.FloatField()


class Candidate(models.Model):
    name = models.CharField()
    number = models.IntegerField()
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("name", "audit")


class TableRegistry(models.Model):
    table_number = models.IntegerField()
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    preliminary_votes = models.IntegerField(default=0)
    audited_votes = models.IntegerField(default=0)

    class Meta:
        unique_together = ("table_number", "candidate")
