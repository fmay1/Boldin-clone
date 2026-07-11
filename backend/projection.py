import math
from database import get_connection

def run_projection(scenario_id):
    """
    Runs a year-by-year projection for a given scenario using a rolling-window
    historical simulation (mean_stdev mode).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Fetch scenario
    cursor.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    if not scenario:
        conn.close()
        return {"error": "Scenario not found"}, 404
        
    # Fetch accounts
    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()
    if not accounts:
        conn.close()
        return {"error": "No accounts found. Please add accounts before running a projection."}, 400
        
    # Fetch annual returns
    cursor.execute("SELECT year, return_pct FROM annual_returns ORDER BY year")
    annual_returns = cursor.fetchall()
    if not annual_returns:
        conn.close()
        return {"error": "No annual return data found. Please upload historical returns."}, 400
        
    conn.close()
    
    # Extract scenario data
    current_age = scenario['current_age']
    retirement_age = scenario['retirement_age']
    end_age = scenario['end_age']
    expenses = scenario['expected_expenses_in_retirement']
    withdrawal_split_pretax_pct = scenario['withdrawal_split_pretax_pct']
    inflation_rate = scenario['inflation_rate_pct'] / 100.0
    return_mode = scenario['return_mode']
    
    if return_mode != 'mean_stdev':
        return {"error": "Only mean_stdev mode is currently supported."}, 400
        
    start_year = scenario['return_start_year']
    end_year = scenario['return_end_year']
    
    if start_year is not None and end_year is not None and start_year > end_year:
        return {"error": "Return start year must be less than or equal to return end year."}, 400
        
    # Build lookup for returns and find last data year
    returns_by_year = {r['year']: r['return_pct'] for r in annual_returns}
    last_data_year = max(returns_by_year.keys())
    
    if end_year is None:
        end_year = last_data_year
        
    # Determine eligible starting years
    eligible_years = [y for y in returns_by_year.keys() if start_year <= y <= end_year]
    if not eligible_years:
        return {"error": "No return data found in the selected year range."}, 400
        
    years_until_retirement = retirement_age - current_age
    projection_horizon = end_age - current_age
    
    # Storage for simulation results per forward year offset
    results_by_offset = {n: [] for n in range(1, projection_horizon + 1)}
    
    # Pre-calculate initial balances and contributions by account type
    initial_post_tax = sum(a['current_balance'] for a in accounts if a['type'] == 'post-tax')
    initial_pretax = sum(a['current_balance'] for a in accounts if a['type'] == 'pre-tax')
    contrib_post_tax = sum(a['annual_contribution'] for a in accounts if a['type'] == 'post-tax')
    contrib_pretax = sum(a['annual_contribution'] for a in accounts if a['type'] == 'pre-tax')
    
    # Track earliest age across all simulations where early pre-tax access occurred
    min_early_access_age = None
    early_access_count = 0
    total_simulations = len(eligible_years)
    
    # Run one simulation per eligible starting year
    for S in eligible_years:
        post_tax = initial_post_tax
        pretax = initial_pretax
        early_pretax_access_age = None
        
        for n in range(1, projection_horizon + 1):
            historical_year = S + n - 1
            
            # Stop simulation if we run out of historical data
            if historical_year > last_data_year:
                break
                
            # Step 3c: Contributions or Withdrawals (applied before growth)
            if n <= years_until_retirement:
                post_tax += contrib_post_tax
                pretax += contrib_pretax
            else:
                age = current_age + n
                withdrawal_need = expenses * ((1 + inflation_rate) ** n)
                
                if age < 59.5:
                    if post_tax >= withdrawal_need:
                        post_tax -= withdrawal_need
                    else:
                        # Fallback to pretax
                        shortfall = withdrawal_need - post_tax
                        post_tax = 0.0
                        if pretax >= shortfall:
                            pretax -= shortfall
                        else:
                            pretax = 0.0
                        if early_pretax_access_age is None:
                            early_pretax_access_age = age
                else:
                    # Split withdrawal by percentage
                    pretax_withdrawal = withdrawal_need * (withdrawal_split_pretax_pct / 100.0)
                    posttax_withdrawal = withdrawal_need * (1.0 - withdrawal_split_pretax_pct / 100.0)
                    
                    pretax -= min(pretax_withdrawal, pretax)
                    post_tax -= min(posttax_withdrawal, post_tax)
                    
            # Step 3d: Apply growth from actual historical return
            ret_pct = returns_by_year[historical_year] / 100.0
            post_tax *= (1 + ret_pct)
            pretax *= (1 + ret_pct)
            
            # Floor at zero
            post_tax = max(0.0, post_tax)
            pretax = max(0.0, pretax)
            
            # Step 3e: Record balances for this offset
            results_by_offset[n].append({
                "combined": post_tax + pretax,
                "post_tax": post_tax,
                "pretax": pretax
            })
            
        # After simulation finishes, check if it triggered early access
        if early_pretax_access_age is not None:
            early_access_count += 1
            if min_early_access_age is None or early_pretax_access_age < min_early_access_age:
                min_early_access_age = early_pretax_access_age
            
    # Step 4: Aggregate across simulations per offset
    final_results = []
    max_covered_offset = 0
    warning = None
    
    for n in range(1, projection_horizon + 1):
        vals = results_by_offset[n]
        if not vals:
            break
            
        max_covered_offset = n
        combined_vals = [v["combined"] for v in vals]
        post_tax_vals = [v["post_tax"] for v in vals]
        pretax_vals = [v["pretax"] for v in vals]
        
        mean = sum(combined_vals) / len(combined_vals)
        variance = sum((x - mean) ** 2 for x in combined_vals) / len(combined_vals)
        stdev = math.sqrt(variance)
        
        mean_post_tax = sum(post_tax_vals) / len(post_tax_vals)
        mean_pretax = sum(pretax_vals) / len(pretax_vals)
        
        # Confidence bands
        ci50_low = mean - 0.674 * stdev
        ci50_high = mean + 0.674 * stdev
        ci70_low = mean - 1.036 * stdev
        ci70_high = mean + 1.036 * stdev
        ci95_low = mean - 1.96 * stdev
        ci95_high = mean + 1.96 * stdev
        
        final_results.append({
            "age": current_age + n,
            "mean_balance": mean,
            "mean_post_tax": mean_post_tax,
            "mean_pretax": mean_pretax,
            "stdev_balance": stdev,
            "ci50_low": ci50_low,
            "ci50_high": ci50_high,
            "ci70_low": ci70_low,
            "ci70_high": ci70_high,
            "ci95_low": ci95_low,
            "ci95_high": ci95_high
        })
        
    # Step 5: Warning if horizon not fully covered
    if max_covered_offset < projection_horizon:
        warning = f"Selected starting-year range doesn't cover the full projection horizon. Results shown only through age {current_age + max_covered_offset}."
        
    # Step 6: Warning for early pre-tax access
    early_access_warning = None
    if min_early_access_age is not None:
        pct = (early_access_count / total_simulations) * 100
        early_access_warning = f"In {early_access_count} out of {total_simulations} historical scenarios ({pct:.1f}%), pre-tax funds were accessed before age 59.5 because post-tax funds ran out, starting as early as age {min_early_access_age}."
        
    return {
        "results": final_results,
        "warning": warning,
        "early_access_warning": early_access_warning
    }
