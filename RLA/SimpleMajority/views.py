import random
from decimal import Decimal

import pandas as pd
from django.shortcuts import render, redirect

from RLA import utils
from RLA.utils import validated, SPRT
# Create your views here.
from SimpleMajority.forms import RecountForm
from audit.models import Audit, BRAVOAudit, Candidate, RecountRegistry


def create_simple_majority_audit(form):
    audit = form.save()
    df = pd.read_csv(form.cleaned_data['preliminary_count_file'])
    subaudit = BRAVOAudit(
        audit=audit,
        winners=form.cleaned_data['n_winners']
    )
    candidates = df.groupby('candidate').sum()['votes'].sort_values(ascending=False).keys()
    W = candidates[:audit.n_winners]
    L = candidates[audit.n_winners:]
    subaudit.T = {w: {l: Decimal(1.0) for l in L} for w in W}
    subaudit.save()
    # csv file with columns: mesa, candidato, votos
    shuffled = []
    table_count = df.groupby('table').sum()['votes'].to_dict()
    for table in table_count:
        shuffled.extend(zip([table] * table_count[table], range(table_count[table])))

    # TODO replace with shuffle after seed
    random.shuffle(shuffled)
    audit.shuffled = shuffled
    audit.save()
    for candidate_name in df['candidate'].unique():
        candidate = Candidate(
            name=candidate_name,
            subaudit=subaudit
        )
        candidate.save()

    return redirect(f'/simplemajority/preliminary/{audit.pk}')


def preliminary_view(request, audit_pk):
    audit = Audit.objects.get(pk=audit_pk)
    df = pd.read_csv(audit.preliminary_count)
    vote_count = df.groupby('candidate').sum()['votes'].to_dict()
    context = {
        'vote_count': vote_count,
        'audit_pk': audit_pk
    }
    return render(request, 'SimpleMajority/preliminary_view.html', context)


def recount_view(request, audit_pk):
    audit = Audit.objects.get(pk=audit_pk)
    preliminary = pd.read_csv(audit.preliminary_count)
    vote_count = preliminary.groupby('candidate').sum()['votes'].to_dict()
    votes = list(vote_count.values())
    votes.sort(reverse=True)
    sample_size = utils.ASN(
        audit.risk_limit,
        votes[audit.n_winners - 1],
        votes[audit.n_winners],
        preliminary['votes'].sum()
    )
    form = RecountForm(initial={'recounted_ballots': sample_size})
    if request.method == 'POST':
        form = RecountForm(request.POST, request.FILES)
        if form.is_valid():
            recount_registry = RecountRegistry(
                audit=audit,
                recount=form.cleaned_data['recount']
            )
            recount_registry.save()
            subaudit = audit.subaudit_set.first()
            recount = pd.read_csv(recount_registry.recount)
            vote_recount = recount.groupby('candidate').sum()['votes'].to_dict()
            subaudit.T = SPRT(vote_count, vote_recount, subaudit.T, audit.risk_limit)
            subaudit.save()
            return redirect(f'/simplemajority/validated/{audit_pk}/')

    sample = audit.shuffled[:sample_size]
    tables = {}
    for table, ballot in sample:
        if table not in tables:
            tables[table] = []

        tables[table].append(ballot)

    for table in tables:
        tables[table].sort()

    tables = {table: tables[table] for table in sorted(tables)}
    context = {
        'form': form,
        'tables': tables,
        'sample_size': sample_size,
        'audit_pk': audit_pk
    }
    return render(request, 'SimpleMajority/recount_template.html', context)


def validated_view(request, audit_pk):
    audit = Audit.objects.get(pk=audit_pk)
    df = pd.read_csv(audit.preliminary_count)
    vote_count = df.groupby('candidate').sum()['votes'].to_dict()
    subaudit = audit.subaudit_set.first()
    recount = {candidate: 0 for candidate in df['candidate'].unique()}
    for r in audit.recountregistry_set.all():
        rc = pd.read_csv(r.recount)
        rec = rc.groupby('candidate').sum()['votes'].to_dict()
        for candidate in rec:
            recount[candidate] += rec[candidate]

    is_validated = validated(subaudit.T, audit.risk_limit)
    max_p_value = 0
    for w in subaudit.T:
        for l in subaudit.T[w]:
            max_p_value = max(max_p_value, 1 / subaudit.T[w][l])

    if is_validated:
        audit.in_progress = False
        audit.save()

    context = {
        'vote_count': vote_count,
        'recount': recount,
        'is_validated': is_validated,
        'max_p_value': max_p_value,
        'recount_url': f'/simplemajority/recount/{audit_pk}/'
    }
    return render(request, 'audit/validate_template.html', context)
