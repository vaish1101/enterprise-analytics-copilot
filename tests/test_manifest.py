import csv
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / "data/source_manifest.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.fieldnames = set(reader.fieldnames or [])
            self.rows = list(reader)

    def test_manifest_has_required_fields_and_expected_rows(self):
        required = {
            "source_id", "company", "source_type", "reporting_period", "publication_date",
            "official_url", "expected_filename", "acquisition_method", "acquisition_status",
            "expected_content_type", "hash_algorithm", "sha256", "retrieval_timestamp",
        }
        self.assertTrue(required.issubset(self.fieldnames))
        self.assertEqual(6, len(self.rows))

    def test_source_ids_are_unique_and_urls_are_official_https(self):
        ids = [row["source_id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        allowed_hosts = {"www.henkel.com", "group.mercedes-benz.com", "assets.new.siemens.com"}
        for row in self.rows:
            parsed = urlparse(row["official_url"])
            self.assertEqual("https", parsed.scheme)
            self.assertIn(parsed.hostname, allowed_hosts)

    def test_integrity_metadata_matches_acquisition_state(self):
        for row in self.rows:
            self.assertEqual("SHA-256", row["hash_algorithm"])
            if row["acquisition_status"].startswith("acquired"):
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(row["retrieval_timestamp"])
                self.assertGreater(int(row["byte_size"]), 0)
            else:
                self.assertFalse(row["sha256"])

    def test_raw_sources_are_gitignored(self):
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/data/raw_sources/", patterns)


if __name__ == "__main__":
    unittest.main()
