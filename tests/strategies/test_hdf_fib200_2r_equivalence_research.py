from tools.research_dvp_fib200_2r_equivalence import geometry


def test_exact_equivalence_requires_zero_displacement_and_zero_stop_buffer():
    out = geometry(level=2.0, width=1.0, entry_displacement=0.0, stop_buffer=0.0)
    assert out.fib_r == 2.0
    assert out.benchmark_minus_fib == 0.0


def test_entry_displacement_breaks_fib200_2r_equivalence():
    out = geometry(level=2.0, width=1.0, entry_displacement=0.05, stop_buffer=0.0)
    assert round(out.fib_r, 6) == 1.857143
    assert round(out.benchmark_minus_fib, 6) == 0.15


def test_stop_buffer_breaks_fib200_2r_equivalence():
    out = geometry(level=2.0, width=1.0, entry_displacement=0.0, stop_buffer=0.05)
    assert round(out.fib_r, 6) == 1.904762
    assert round(out.benchmark_minus_fib, 6) == 0.10


def test_fib200_can_fall_to_entry_when_gap_equals_two_pattern_widths():
    out = geometry(level=2.0, width=1.0, entry_displacement=2.0, stop_buffer=0.0)
    assert out.fib_distance == 0.0
    assert out.fib_r == 0.0
