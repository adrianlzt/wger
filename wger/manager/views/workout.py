# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

# Standard Library
import copy
import logging
import warnings
import datetime

# Django
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import (
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import (
    get_object_or_404,
    render,
)
from django.template.context_processors import csrf
from django.urls import (
    reverse,
    reverse_lazy,
)
from django.utils.text import slugify
from django.utils.translation import (
    gettext as _,
    gettext_lazy,
)
from django.views.generic import (
    DeleteView,
    UpdateView,
)

# Third Party
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from RestrictedPython import compile_restricted

# wger
from wger.manager.forms import (
    WorkoutCopyForm,
    WorkoutForm,
    WorkoutMakeTemplateForm,
)
from wger.manager.models import (
    Schedule,
    Workout,
    WorkoutLog,
)
from wger.measurements.models import (
    Category,
    Measurement,
)
from wger.weight.models import WeightEntry

from wger.utils.generic_views import (
    WgerDeleteMixin,
    WgerFormMixin,
)
from wger.utils.helpers import make_token


logger = logging.getLogger(__name__)

# ************************
# Workout functions
# ************************


@login_required
def template_overview(request):
    """

    """
    return render(
        request, 'workout/overview.html', {
            'workouts': Workout.templates.filter(user=request.user),
            'title': _('Your templates'),
            'template_overview': True
        }
    )


@login_required
def public_template_overview(request):
    """

    """
    return render(
        request, 'workout/overview.html', {
            'workouts': Workout.templates.filter(is_public=True),
            'title': _('Public templates'),
            'template_overview': True
        }
    )


def view(request, pk):
    """
    Show the workout with the given ID
    """
    workout = get_object_or_404(Workout, pk=pk)
    user = workout.user
    is_owner = request.user == user

    if not is_owner and not user.userprofile.ro_access:
        return HttpResponseForbidden()

    uid, token = make_token(user)

    context = {
        'workout': workout,
        'uid': uid,
        'token': token,
        'is_owner': is_owner,
        'owner_user': user,
        'show_shariff': is_owner,
    }

    return render(request, 'workout/view.html', context)


def autoselect_day(request, pk):
    """
    Given a workout ID, return the day that should be performed today.

    Each day has a "priority" field and a "decision_code" field. The priority
    field is a number that indicates the order in which the days should be
    analyzed. For each day, the decision_code is evaluated. If it returns True,
    the day is selected. If it returns False, the next day is analyzed. If all
    days have been analyzed and none of them returned True, the last day is
    selected.

    Returns the day ID.
    """
    workout = get_object_or_404(Workout, pk=pk)
    user = workout.user
    is_owner = request.user == user

    if not is_owner and not user.userprofile.ro_access:
        return HttpResponseForbidden()

    # Get the days
    days = workout.day_set.all()

    # Sort the days by priority, highest first
    days = sorted(days, key=lambda day: day.priority, reverse=True)

    # Get the day that should be performed today
    today = None
    debug = ""
    for day in days:
        decision, debug = evaluate_day(day.decision_code, user)
        if decision:
            today = day
            break
    if today is None:
        today = days[-1]


    return render(request, 'workout/autoselect.html', {
        'day': today,
        'debug': debug.replace("\n", "<br>"),
    })


@login_required()
def template_view(request, pk):
    """
    Show the template with the given ID
    """
    template = get_object_or_404(Workout.templates, pk=pk)

    if not template.is_public and request.user != template.user:
        return HttpResponseForbidden()

    context = {
        'workout': template,
        'muscles': template.canonical_representation['muscles'],
        'is_owner': template.user == request.user,
        'owner_user': template.user,
    }
    return render(request, 'workout/template_view.html', context)


@login_required
def copy_workout(request, pk):
    """
    Makes a copy of a workout
    """
    workout = get_object_or_404(Workout.both, pk=pk)

    if not workout.is_public and request.user != workout.user:
        return HttpResponseForbidden()

    # Process request
    if request.method == 'POST':
        workout_form = WorkoutCopyForm(request.POST)

        if workout_form.is_valid():

            # Copy workout
            workout_copy: Workout = copy.copy(workout)
            workout_copy.pk = None
            workout_copy.name = workout_form.cleaned_data['name']
            workout_copy.user = request.user
            workout_copy.is_template = False
            workout_copy.is_public = False
            workout_copy.save()

            # Copy the days
            for day in workout.day_set.all():
                day_copy = copy.copy(day)
                day_copy.pk = None
                day_copy.training = workout_copy
                day_copy.save()
                for i in day.day.all():
                    day_copy.day.add(i)
                day_copy.save()

                # Copy the sets
                for current_set in day.set_set.all():
                    current_set_copy = copy.copy(current_set)
                    current_set_copy.pk = None
                    current_set_copy.exerciseday = day_copy
                    current_set_copy.save()

                    # Copy the settings
                    for current_setting in current_set.setting_set.all():
                        setting_copy = copy.copy(current_setting)
                        setting_copy.pk = None
                        setting_copy.set = current_set_copy
                        setting_copy.save()

            return HttpResponseRedirect(workout_copy.get_absolute_url())
    else:
        workout_form = WorkoutCopyForm({'name': workout.name, 'description': workout.description})
        workout_form.helper = FormHelper()
        workout_form.helper.form_id = slugify(request.path)
        workout_form.helper.form_method = 'post'
        workout_form.helper.form_action = request.path
        workout_form.helper.add_input(
            Submit('submit', _('Save'), css_class='btn-success btn-block')
        )
        workout_form.helper.form_class = 'wger-form'

        template_data = {}
        template_data.update(csrf(request))
        template_data['title'] = _('Copy workout')
        template_data['form'] = workout_form
        template_data['form_fields'] = [workout_form['name']]
        template_data['submit_text'] = _('Copy')

        return render(request, 'form.html', template_data)


def make_workout(request, pk):
    workout = get_object_or_404(Workout.both, pk=pk)

    if request.user != workout.user:
        return HttpResponseForbidden()

    workout.is_template = False
    workout.is_public = False
    workout.save()

    return HttpResponseRedirect(workout.get_absolute_url())


@login_required
def add(request):
    """
    Add a new workout and redirect to its page
    """
    workout = Workout()
    workout.user = request.user
    workout.save()

    return HttpResponseRedirect(workout.get_absolute_url())


class WorkoutDeleteView(WgerDeleteMixin, LoginRequiredMixin, DeleteView):
    """
    Generic view to delete a workout routine
    """

    model = Workout
    success_url = reverse_lazy('manager:workout:overview')
    messages = gettext_lazy('Successfully deleted')

    def get_context_data(self, **kwargs):
        context = super(WorkoutDeleteView, self).get_context_data(**kwargs)
        context['title'] = _('Delete {0}?').format(self.object)
        return context


class WorkoutEditView(WgerFormMixin, LoginRequiredMixin, UpdateView):
    """
    Generic view to update an existing workout routine
    """

    model = Workout
    form_class = WorkoutForm

    def get_context_data(self, **kwargs):
        context = super(WorkoutEditView, self).get_context_data(**kwargs)
        context['title'] = _('Edit {0}').format(self.object)
        return context


class WorkoutMarkAsTemplateView(WgerFormMixin, LoginRequiredMixin, UpdateView):
    """
    Generic view to update an existing workout routine
    """

    model = Workout
    form_class = WorkoutMakeTemplateForm

    def get_context_data(self, **kwargs):
        context = super(WorkoutMarkAsTemplateView, self).get_context_data(**kwargs)
        context['title'] = _('Mark as template')
        return context


def evaluate_day(code, user):
    """Given a python code string, execute it and return the result.

    The python code will be executed in a restricted environment.

    Args:
        code (str): Python code to execute
        user (User): User, to filter the values

    Returns:
        (bool, str): Tuple with the result of the code and the debug output
    """
    # TODO in the editor view show the results and errors at edit time.
    # TODO if there is an error executing the code, show the error message to the user
    def get_category_by_name(name):
        return Category.objects.get(name=name, user=user)

    def get_measurements_by_category_name(category_name):
        category = Category.objects.get(name=category_name, user=user)
        return Measurement.objects.filter(category=category)

    def get_measurement_by_name_and_date(category_name, date):
        """Get measurement by name and date

        If there is no measurement for that date, return None.

        Args:
            category_name (str): Category name
            date (datetime.date): Date

        Returns:
            float: Measurement value
        """
        category = Category.objects.get(name=category_name, user=user)
        measurement = None
        try:
             measurement = Measurement.objects.get(category=category, date=date).value
        except:
            pass

        return measurement

    def get_weight_by_date(date):
        """Get weight by date

        If there is no weight for that date, return None.

        Args:
            date (datetime.date): Date

        Returns:
            float: Weight value
        """
        weight = None
        try:
            weight = WeightEntry.objects.get(date=date, user=user).weight
        except:
            pass

        return weight

    # Execute widget code in a restricted environment
    loc = {
        "get_category_by_name": get_category_by_name,
        "get_measurements_by_category_name": get_measurements_by_category_name,
        "get_measurement_by_name_and_date": get_measurement_by_name_and_date,
        "get_weight_by_date": get_weight_by_date,
        "today": datetime.date.today(),
        # Allow to get "prints"
        "_print_": PrintCollector,
        "_getattr_": getattr,
        "_getiter_": iter,
        "decision": False,
    }
    PrintCollector.output = []

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=SyntaxWarning)
        try:
            byte_code = compile_restricted(
                    code,
                    '<string>',
                    'exec',
            )
        except Exception as e:
            return False, str(e)

    try:
        exec(byte_code, loc)
    except Exception as e:
        return False, str(e)

    # Get print output
    print_output = ""
    print_func = loc.get('_print')
    if print_func is not None:
        print_output = print_func()

    decision = loc.get("decision")
    return decision, print_output

# https://stackoverflow.com/a/76214209/1407722
class PrintCollector:
    output = []

    def __init__(self, _getattr_=None):
        self._getattr_ = _getattr_

    def write(self, text):
        PrintCollector.output.append(text)

    def __call__(self):
        return ''.join(PrintCollector.output)

    def _call_print(self, *objects, **kwargs):
        if kwargs.get('file', None) is None:
            kwargs['file'] = self
        else:
            self._getattr_(kwargs['file'], 'write')

        print(*objects, **kwargs)
