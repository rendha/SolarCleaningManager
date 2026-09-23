import pandas as pd

from django.core.management.base import BaseCommand

from cleaning.models import Customer, Site


class Command(BaseCommand):

    help = "Import customers and sites from Excel"


    def add_arguments(self, parser):

        parser.add_argument(
            "excel_file",
            type=str
        )


    def handle(self, *args, **options):

        excel_file = options["excel_file"]

        df = pd.read_excel(excel_file)

        created_customers = 0
        created_sites = 0
        skipped = 0


        for _, row in df.iterrows():

            customer_name = str(
                row.get("Customer Name/", "")
            ).strip()

            if not customer_name or customer_name == "nan":
                skipped += 1
                continue


            contact_person = str(
                row.get("Contact Person", "")
            ).strip()

            if contact_person == "nan":
                contact_person = ""


            phone = str(
                row.get("Phone", "")
            ).strip()

            if phone == "nan":
                phone = ""


            location = str(
                row.get("Location/Site", "")
            ).strip()

            if location == "nan":
                location = ""


            address = str(
                row.get("              Address", "")
            ).strip()

            if address == "nan":
                address = ""


            solar_kw = str(
                row.get("Solar KW", "")
            ).strip()

            if solar_kw == "nan":
                solar_kw = ""


            google_map_link = str(
                row.get("       Google Map link", "")
            ).strip()

            if google_map_link == "nan":
                google_map_link = ""


            customer, created = Customer.objects.get_or_create(
                name=customer_name,
                defaults={
                    "contact_person": contact_person,
                    "phone": phone,
                }
            )


            if created:

                created_customers += 1

            else:

                changed = False

                if contact_person and not customer.contact_person:
                    customer.contact_person = contact_person
                    changed = True

                if phone and not customer.phone:
                    customer.phone = phone
                    changed = True

                if changed:
                    customer.save()


            Site.objects.get_or_create(
                customer=customer,
                location=location,
                address=address,
                defaults={
                    "solar_kw": solar_kw,
                    "google_map_link": google_map_link,
                }
            )

            created_sites += 1


        self.stdout.write(
            self.style.SUCCESS(
                f"""
IMPORT COMPLETE!

Customers created: {created_customers}
Sites processed: {created_sites}
Rows skipped: {skipped}
"""
            )
        )