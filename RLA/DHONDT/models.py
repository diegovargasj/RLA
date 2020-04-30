from django.db import models

# Create your models here.
from audit.models import SubAudit, PseudiCandidate


class DHONDTAudit(SubAudit):
    seats = models.IntegerField()


class Party(PseudiCandidate):
    subaudit = models.ForeignKey(DHONDTAudit, on_delete=models.PROTECT)


class PartyMember(PseudiCandidate):
    members_party = models.ForeignKey(Party, on_delete=models.PROTECT)
