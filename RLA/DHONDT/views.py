from django.shortcuts import render, redirect

from DHONDT.forms import CreateDHONDTForm
from RLA.utils import p


def get_W_L_sets(vote_count, S):
    """
    Returns the reported winning and losing sets of parties
    @param vote_count   :   {dict<models.Party->int>}
                            Dictionary with the reported number of votes
                            per party
    @param S            :   {int}
                            Number of seats being competed for
    @return             :   {tuple<list<models.Party>, list<models.Party>>}
                            Tuple with the reported winning and losing
                            sets of parties
    """
    full_set = []
    for i in range(1, S + 1):
        for party in list(vote_count.keys()):
            full_set.append((party, i))

    sorted_tuples = sorted(full_set, key=(lambda x: p(x[0], vote_count, x[1])), reverse=True)
    W = sorted_tuples[:S]
    L = sorted_tuples[S:]
    return W, L


def create_view(request):
    form = CreateDHONDTForm()
    if request.method == 'POST':
        form = CreateDHONDTForm(request.POST)
        if form.is_valid():
            audit = form.save()
            return redirect(f'/dhondt/preliminary/{audit.pk}/')

    context = {
        'form': form,
        'action': '/dhondt/create/'
    }
    return render(request, 'audit/form_template.html', context)


def preliminary_view(request, audit_pk):
    if request.method == 'POST':
        pass

    context = {
        'action': f'/dhondt/preliminary/{audit_pk}/'
    }
    return render(request, 'audit/form_template.html', context)


def recount_view(request):
    pass


def validated_view(request):
    pass
