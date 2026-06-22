from django.core.management.base import BaseCommand

from api.services.shop_data import load_shop_data


class Command(BaseCommand):
    help = "Load or update shop YAML data without duplicating existing offers"

    def add_arguments(self, parser):
        parser.add_argument(
            "yaml_file",
            type=str,
            help="Path to YAML file with shop, categories and goods sections.",
        )

    def handle(self, *_, **options):
        result = load_shop_data(options["yaml_file"])
        for message in result.skipped_messages:
            self.stderr.write(message)

        self.stdout.write(
            self.style.SUCCESS(f"Data loaded successfully: {result.loaded_count} goods")
        )
