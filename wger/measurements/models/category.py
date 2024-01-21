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

# Django
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):

    class Meta:
        ordering = [
            "-name",
        ]

    user = models.ForeignKey(
        User,
        verbose_name=_('User'),
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        verbose_name=_('Name'),
        max_length=100,
    )

    unit = models.CharField(
        verbose_name=_('Unit'),
        max_length=30,
    )

    description = models.TextField(
        verbose_name=_('Description'),
        null=True,
        blank=True,
    )

    code = models.TextField(
        verbose_name=_('Code'),
        null=True,
        blank=True,
    )
    """Python code to calculate the value.
    Instead of storing a single value, store a python code that could be used
    to calculate a value based on other values, user profile, etc"""

    def get_owner_object(self):
        """
        Returns the object that has owner information
        """
        return self
