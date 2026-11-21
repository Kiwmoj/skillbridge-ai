import unittest

from services.career_catalog import CAREERS_BY_INDUSTRY, CAREER_NAMES, INDUSTRIES, infer_industry


class CareerCatalogTests(unittest.TestCase):
    def test_search_catalog_covers_requested_industries_and_custom_roles(self):
        expected = {
            "Technology": ["Software Engineer", "AI Engineer", "Data Scientist", "Cybersecurity Analyst", "Robotics Engineer", "Electrical Engineer", "Mechanical Engineer"],
            "Creative Industries": ["Video Game Animator", "3D Character Artist", "Game Developer", "Graphic Designer", "UI/UX Designer", "Film Editor", "VFX Artist", "Architect"],
            "Business": ["Entrepreneur", "Marketing Manager", "Financial Analyst", "Business Analyst", "Project Manager"],
            "Science": ["Biomedical Engineer", "Aerospace Engineer", "Environmental Scientist", "Research Scientist"],
            "Healthcare": ["Pharmacist", "Nurse", "Physical Therapist", "Medical Researcher"],
        }
        self.assertEqual(CAREERS_BY_INDUSTRY, expected)
        self.assertTrue(set(INDUSTRIES).issuperset(expected))
        self.assertIn("Data Scientist", CAREER_NAMES)
        self.assertEqual(infer_industry("Marine Biologist"), "Other / custom")
        self.assertEqual(infer_industry("Nurse"), "Healthcare")


if __name__ == "__main__":
    unittest.main()
