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
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.

# Standard Library
import logging
import warnings
from datetime import datetime

# Third Party
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from RestrictedPython import compile_restricted
from RestrictedPython import utility_builtins

# wger
from wger.measurements.api.serializers import (
    MeasurementSerializer,
    UnitSerializer,
)
from wger.measurements.models import (
    Category,
    Measurement,
)
from wger.weight.models import WeightEntry


logger = logging.getLogger(__name__)


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

class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for measurement units
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UnitSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = ['id', 'name', 'unit', 'description', 'code']

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()

        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the owner
        """
        serializer.save(user=self.request.user)


class TestCodeViewSet(viewsets.ViewSet):
    def create(self, request, *args, **kwargs):
        return execute_code(request.data.get("code"), 1, user=self.request.user)


class MeasurementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for measurements
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MeasurementSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = [
        'id',
        'category',
        'date',
        'value',
    ]

    def list(self, request, *args, **kwargs):
        # Get the ID of the category
        category_id = request.GET.get('category', None)
        # Use that ID to get the category name
        category_code = Category.objects.get(id=category_id).code

        if category_code and category_code != '':
            return execute_code(category_code, category_id, user=self.request.user)

        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, "swagger_fake_view", False):
            return Measurement.objects.none()

        return Measurement.objects.filter(category__user=self.request.user)


def execute_code(code, category_id, user):
    """Given a python code string, execute it and return the results.

    The python code will be executed in a restricted environment.

    Category id is needed to format the results.

    Args:
        code (str): Python code to execute
        category_id (int): Category ID
        user (User): User, to filter the values

    Returns:
        Response: Response with the results, same format as list view for measurements
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

        Args:
            category_name (str): Category name
            date (datetime.date): Date

        Returns:
            float: Measurement value
        """
        category = Category.objects.get(name=category_name, user=user)
        return Measurement.objects.get(category=category, date=date).value

    def get_weight_by_date(date):
        """Get weight by date

        Args:
            date (datetime.date): Date

        Returns:
            float: Weight value
        """
        return WeightEntry.objects.get(date=date, user=user).weight

    # Execute widget code in a restricted environment
    loc = {
        "get_category_by_name": get_category_by_name,
        "get_measurements_by_category_name": get_measurements_by_category_name,
        "get_measurement_by_name_and_date": get_measurement_by_name_and_date,
        "get_weight_by_date": get_weight_by_date,
        # Allow to get "prints"
        "_print_": PrintCollector,
        "_getattr_": getattr,
        "_getiter_": iter,
        "results": [],
    }
    PrintCollector.output = []

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=SyntaxWarning)
        byte_code = compile_restricted(
                code,
                '<string>',
                'exec',
        )

    try:
        exec(byte_code, loc)
    except Exception as e:
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            "print": None,
            "error": str(e),
        }) # TODO make the UI to handle the error correctly
        # }, status=401)

    # For each result in results, add the category id and an incrementing id
    for i, result in enumerate(loc.get("results", [])):
        result["category"] = int(category_id)
        result["id"] = i + 1

    # Get print output
    print_output = None
    print_func = loc.get('_print')
    if print_func is not None:
        print_output = print_func()

    return Response({
        'count': 0,
        'next': None,
        'previous': None,
        'results': loc.get("results", []),
        "print": print_output,
    })
