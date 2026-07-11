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
        
    # Convert ages to months for precise monthly simulation (per Section 4a)
    retirement_month = round((retirement_age - current_age) * 12)
    total_months = int((end_age - current_age) * 12)
    
    # Determine target ages for reporting results
    # Whole years from current_age up to retirement_age, plus retirement_age if fractional,
    # then whole years from retirement_age to end_age.
    target_ages = []
    age = math.floor(current_age) + 1
    while age < retirement_age:
        target_ages.append(age)
        age += 1
    if retirement_age != int(retirement_age):
        target_ages.append(retirement_age)
    age = math.ceil(retirement_age)
    while age <= end_age:
        target_ages.append(age)
        age += 1
        
    # Map target ages to month indices for recording
    target_months = {round((A - current_age) * 12): A for A in target_ages}
    results_by_age = {A: [] for A in target_ages}
    
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
        
        for m in range(1, total_months + 1):
            historical_year = S + (m - 1) // 12
            
            # Stop simulation if we run out of historical data
            if historical_year > last_data_year:
                break
                
            # 1. Get annual return and convert to monthly rate (geometric)
            ret_pct = returns_by_year[historical_year] / 100.0
            monthly_rate = (1 + ret_pct) ** (1/12) - 1
            
            # 2. Determine phase and monthly amounts
            is_pre_retirement = m <= retirement_month
            age_this_month = current_age + (m - 1) / 12.0
            
            if is_pre_retirement:
                monthly_contrib_post = contrib_post_tax / 12.0
                monthly_contrib_pretax = contrib_pretax / 12.0
            else:
                years_elapsed = (m - 1) / 12.0
                annual_withdrawal = expenses * ((1 + inflation_rate) ** years_elapsed)
                monthly_withdrawal = annual_withdrawal / 12.0
            
            # 3. Run monthly iteration
            # a. Grow balances by monthly rate
            post_tax *= (1 + monthly_rate)
            pretax *= (1 + monthly_rate)
            
            # b. Apply contribution or withdrawal
            if is_pre_retirement:
                post_tax += monthly_contrib_post
                pretax += monthly_contrib_pretax
            else:
                if age_this_month < 59.5:
                    if post_tax >= monthly_withdrawal:
                        post_tax -= monthly_withdrawal
                    else:
                        shortfall = monthly_withdrawal - post_tax
                        post_tax = 0.0
                        if pretax >= shortfall:
                            pretax -= shortfall
                        else:
                            pretax = 0.0
                        if early_pretax_access_age is None:
                            early_pretax_access_age = age_this_month
                else:
                    pretax_withdrawal = monthly_withdrawal * (withdrawal_split_pretax_pct / 100.0)
                    posttax_withdrawal = monthly_withdrawal * (1.0 - withdrawal_split_pretax_pct / 100.0)
                    
                    pretax -= min(pretax_withdrawal, pretax)
                    post_tax -= min(posttax_withdrawal, post_tax)
            
            # Floor at zero
            post_tax = max(0.0, post_tax)
            pretax = max(0.0, pretax)
            
            # Record balances at target ages
            if m in target_months:
                target_age = target_months[m]
                results_by_age[target_age].append({
                    "combined": post_tax + pretax,
                    "post_tax": post_tax,
                    "pretax": pretax
                })
            
        # After simulation finishes, check if it triggered early access
        if early_pretax_access_age is not None:
            early_access_count += 1
            if min_early_access_age is None or early_pretax_access_age < min_early_access_age:
                min_early_access_age = early_pretax_access_age
            
    # Step 4: Aggregate across simulations per target age
    final_results = []
    max_covered_age = None
    warning = None
    
    for target_age in target_ages:
        vals = results_by_age[target_age]
        # Require at least 5 simulations to report a statistically meaningful data point
        if len(vals) < 5:
            break
            
        max_covered_age = target_age
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
            "age": target_age,
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
        
    # Step 5: Warning if horizon not fully covered (due to data limits or <5 simulations)
    if max_covered_age is not None and max_covered_age < end_age:
        warning = f"Selected starting-year range doesn't cover the full projection horizon. Results shown only through age {max_covered_age}."
        
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
