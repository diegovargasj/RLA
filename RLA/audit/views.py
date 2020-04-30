# Create your views here.
import operator
from decimal import getcontext

from django.http import Http404
from django.shortcuts import render, redirect

from SimpleMajority.views import create_simple_majority_audit
from audit.forms import CreateAuditForm
from audit.models import Audit


def init_subaudit(request):
    getcontext().prec = 100


def landing_page_view(request):
    audits = Audit.objects.all().order_by('date')
    context = {'audits': audits}
    return render(request, 'audit/list_audits.html', context)


def create_audit_view(request):
    form = CreateAuditForm()
    if request.method == 'POST':
        form = CreateAuditForm(request.POST, request.FILES)
        if form.is_valid():
            if form.cleaned_data['election_type'] == 'simplemajority':
                return create_simple_majority_audit(form)

            elif form.cleaned_data['election_type'] == 'supermajority':
                # audit = create_super_majority_audit_view(form)
                template = 'SuperMajority/preliminary_view.html'
                return Http404('Not implemented yet')

            else:  # form.cleaned_data['election_type'] == 'dhondt':
                # audit = create_dhondt_audit_view(form)
                template = 'DHONDT/preliminary_view.html'
                return Http404('Not implemented yet')

    context = {
        'form': form,
        'action': '/new/'
    }
    return render(request, 'audit/form_template.html', context)


def view_audit_view(request, audit_pk):
    audit = Audit.objects.get(pk=audit_pk)
    context = {'audit': audit}
    return render(request, 'audit/view_audit.html', context)


######################### BRAVO ######################################


def BRAVO_get_W_L_sets(vote_count, n_winners):
    """
    Obtains the winner and loser sets, given the amount of votes
    for each candidate
    @param vote_count   :   {dict<models.Candidate->int>}
                            Dictionary with the reported amount of votes
                            per candidate
    @param n_winners    :   {int}
                            Number of winners for the election
    @return             :   {tuple<list<models.Candidate>,list<models.Candidate>}
                            Tuple with the winners and losers sets
    """
    tuples = list(vote_count.items())
    sorted_tuples = sorted(tuples, key=operator.itemgetter(1), reverse=True)
    W = [c[0] for c in sorted_tuples[:n_winners]]
    L = [c[0] for c in sorted_tuples[n_winners:]]
    return W, L
