"""verifier_mutants.py must not read a skipped killing test as an inert guard.

2026-10-03: on a host without ssh-keygen the `signature` mutant read SURVIVED because the tests
that kill it were skipped; with ssh-keygen installed it read KILLED. A pass with skips is UNDECIDED.
The last case is the anti-vacuity control: a pass with no skips must still read SURVIVED, or the
tool could no longer report an inert guard at all.
"""
import importlib.util, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("verifier_mutants",
                                              os.path.join(ROOT, "tools", "verifier_mutants.py"))
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)


def test_failing_tests_kill_the_mutant_whatever_was_skipped():
    assert vm.classify(1, 0) == "KILLED"
    assert vm.classify(1, 7) == "KILLED"


def test_pass_with_skips_is_undecided_not_survived():
    assert vm.classify(0, 1) == "UNDECIDED"
    assert vm.classify(0, 11) == "UNDECIDED"


def test_pass_with_no_skips_still_reports_survived():
    assert vm.classify(0, 0) == "SURVIVED"


def test_pytest_errors_stay_errors():
    assert vm.classify(2, 0).startswith("ERROR")
    assert vm.classify(5, 3).startswith("ERROR")


def test_skip_count_reads_the_pytest_summary_line():
    assert vm.skip_count("....\n440 passed, 13 skipped in 37.11s\n") == 13
    assert vm.skip_count("....\n452 passed in 39.52s\n") == 0
    assert vm.skip_count("") == 0
