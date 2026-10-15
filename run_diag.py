import pytest
import sys

pytest.main(["-v", "backend/tests/test_trustee_ceremony.py::test_trustee_roster_validation_and_uniqueness", "--tb=short"])
