"""py manage.py add_portal_users  -  brings the portal's people into the Cleaning Manager so they sign in with the same login.

It reads  ../dehlsen_portal/db.sqlite3  (or  --portal PATH)  and copies every account (username, name, PASSWORD, owner/employee setting, groups).
A person who is already here is kept as he or she is (nothing is changed except missing details, extra groups and owner power).
If the portal file cannot be found, the people below are made with  username = name in small letters,  password = name + "dehlsen".
Imran is always set to  Imran / imrandehlsen.   Look first, change nothing:  --dry-run
"""
import datetime
import sqlite3
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

FIELDS = ["username", "password", "first_name", "last_name", "email", "is_staff", "is_superuser", "is_active", "date_joined", "last_login"]

# used only when the portal's database is not found
PEOPLE = ["Siraj", "Fousan", "Hudha", "Riswan", "Junaid", "Ziyad", "Aswanth", "Fidha", "Anoop", "Hari", "Robins",
          "Anupama", "Satheesh", "Rijul"]
RESET_PASSWORDS = {"Imran": "imrandehlsen"}


def as_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        value = parse_datetime(value)
    if value is not None and timezone.is_naive(value):
        value = timezone.make_aware(value, datetime.timezone.utc)
    return value


def read_portal(path):
    connection = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        users, ids = {}, {}
        for row in connection.execute("SELECT * FROM auth_user"):
            data = dict(row)
            users[data["username"]] = data
            ids[data["id"]] = data["username"]
        groups = {}
        try:
            names = {r["id"]: r["name"] for r in connection.execute("SELECT id, name FROM auth_group")}
            for r in connection.execute("SELECT user_id, group_id FROM auth_user_groups"):
                if r["user_id"] in ids and r["group_id"] in names:
                    groups.setdefault(ids[r["user_id"]], []).append(names[r["group_id"]])
        except sqlite3.Error:
            pass
        return users, groups
    finally:
        connection.close()


class Command(BaseCommand):
    help = "Copies the portal's users (with passwords and groups) into the Cleaning Manager."

    def add_arguments(self, parser):
        parser.add_argument("--portal", default=str(Path(settings.BASE_DIR).parent / "dehlsen_portal" / "db.sqlite3"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()
        path = Path(options["portal"])
        rows, groups = {}, {}
        if path.exists():
            try:
                rows, groups = read_portal(path)
                self.stdout.write("Portal database: %d user(s) found." % len(rows))
            except sqlite3.Error as error:
                self.stdout.write(self.style.WARNING("Portal database could not be read (%s)." % error))
        else:
            self.stdout.write(self.style.WARNING("No portal database at %s, so the names in PEOPLE are made instead." % path))

        if options["dry_run"]:
            for name, row in sorted(rows.items(), key=lambda x: x[0].lower()):
                here = User.objects.filter(username__iexact=name).exists() or bool(row.get("first_name") and User.objects.filter(first_name__iexact=row["first_name"]).exists())
                self.stdout.write("  %-14s %s" % (name, "already here" if here else "would be added"))
            self.stdout.write("Dry run: nothing was changed.")
            return

        added, kept = [], []
        with transaction.atomic():
            for name, row in rows.items():
                existing = User.objects.filter(username__iexact=name).first()
                if existing is None and row.get("first_name"):
                    existing = User.objects.filter(first_name__iexact=row["first_name"]).first()
                if existing:
                    existing.is_staff = existing.is_staff or bool(row.get("is_staff"))
                    existing.is_superuser = existing.is_superuser or bool(row.get("is_superuser"))
                    for f in ("first_name", "last_name", "email"):
                        if not getattr(existing, f) and row.get(f):
                            setattr(existing, f, row[f])
                    existing.save()
                    user = existing
                    kept.append(name)
                else:
                    values = {f: row.get(f) for f in FIELDS if f in row}
                    for flag in ("is_staff", "is_superuser", "is_active"):
                        values[flag] = bool(values.get(flag))
                    values["date_joined"] = as_datetime(values.get("date_joined")) or timezone.now()
                    values["last_login"] = as_datetime(values.get("last_login"))
                    user = User.objects.create(**values)
                    added.append(name)
                for group_name in groups.get(name, []):
                    group, _ = Group.objects.get_or_create(name=group_name)
                    user.groups.add(group)

            if not rows:
                for name in PEOPLE:
                    if User.objects.filter(username__iexact=name).exists() or User.objects.filter(first_name__iexact=name).exists():
                        kept.append(name)
                        continue
                    login = name.lower().replace(" ", "")
                    user = User(username=login, first_name=name)
                    user.set_password(login + "dehlsen")
                    user.save()
                    added.append("%s (password %sdehlsen)" % (login, login))

            for name, password in RESET_PASSWORDS.items():
                user = User.objects.filter(username__iexact=name).first() or User.objects.filter(first_name__iexact=name).first()
                if user is None:
                    user = User(username=name, first_name=name)
                user.set_password(password)
                user.is_staff = False          # a director signs in as a normal person here: only Fidha (and superusers) get the owner dashboard
                user.is_superuser = False
                user.save()
                self.stdout.write(self.style.SUCCESS("%s: login is %s / %s" % (name, user.username, password)))

        self.stdout.write(self.style.SUCCESS("Done: %d added, %d already here (kept)." % (len(added), len(kept))))
        if added:
            self.stdout.write("Added: " + ", ".join(added))
