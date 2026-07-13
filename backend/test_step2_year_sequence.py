import sys
import os

# Ensure the backend directory is in the path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from projection import _run_monthly_simulation

def test_year_sequence_override():
    # Mock historical returns data
    returns = {2000: 10.0, 2001: -5.0, 2002: 8.0, 2003: 12.0}
    # Target months map elapsed month index -> target age
    target_months = {12: 47, 24: 48}
    
    # 1. Test default behavior (no sequence provided)
    # Should increment years from start_year (2000) -> 2000, 2001, 2002...
    res1, _ = _run_monthly_simulation(
        start_year=2000,
        current_age=46.0,
        retirement_age=50.0,
        end_age=60.0,
        expenses=50000,
        withdrawal_split_pretax_pct=50,
        inflation_rate=0.025,
        initial_post_tax=100000,
        initial_pretax=100000,
        contrib_post_tax=10000,
        contrib_pretax=10000,
        returns_by_year=returns,
        last_data_year=2003,
        target_months=target_months
    )
    print('Default (increments from 2000):', list(res1.keys()))
    
    # 2. Test with explicit year_sequence (Monte Carlo style)
    # Forces specific years per period: period 0 -> 2002, period 1 -> 2000, period 2 -> 2001
    custom_seq = [2002, 2000, 2001]
    res2, _ = _run_monthly_simulation(
        start_year=2000, # Ignored when year_sequence is provided
        current_age=46.0,
        retirement_age=50.0,
        end_age=60.0,
        expenses=50000,
        withdrawal_split_pretax_pct=50,
        inflation_rate=0.025,
        initial_post_tax=100000,
        initial_pretax=100000,
        contrib_post_tax=10000,
        contrib_pretax=10000,
        returns_by_year=returns,
        last_data_year=2003,
        target_months=target_months,
        year_sequence=custom_seq
    )
    print('Custom sequence:', list(res2.keys()))
    
    # Verify they differ (proves the sequence is actually being used)
    if res1 != res2:
        print('✅ Step 2 verified: year_sequence correctly overrides default year assignment.')
    else:
        print('❌ Test failed: Results should differ when using a custom year_sequence.')
        sys.exit(1)

if __name__ == '__main__':
    test_year_sequence_override()
