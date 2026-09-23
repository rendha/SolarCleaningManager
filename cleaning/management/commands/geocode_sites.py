from django.core.management.base import BaseCommand
from cleaning.models import site
from geopy.geocoders import Nominatim
from time import sleep

class Command(BaseCommand):
    help =