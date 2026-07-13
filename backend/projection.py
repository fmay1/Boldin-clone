import math
import random
from database import get_connection

def _percentile(sorted_data, p):
    """Compute the p-th percentile of sorted_data using linear interpolation."""
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_data[0]
    idx = (p / 100.0) * (n - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return sorted_data[lower]
    frac = idx - lower
    return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac

def _run_monthly_simulation(start_year, current_age, retirement_age, end_age, expenses, withdrawal_split_pretax_pct, inflation_rate, initial_post_tax, initial_pretax, contrib_post_tax, contrib_pretax, returns_by_year, last_data_year, target_months, expenditures=None, incomes=None, year_sequence=None):
    """
    Runs a single monthly simulation starting from a given historical year.
    If year_sequence is provided (e.g., for Monte Carlo), it uses that sequence
    instead of incrementing from start_year.
    Returns a dict of {target_age: {combined, post_tax, pretax}} and the early_pretax_access_age if any.
    """
    if expenditures is None:
        expenditures = []
    if incomes is None:
        incomes = []
        
    post_tax = initial_post_tax
    pretax = initial_pretax
    early_pretax_access_age = None
    
    retirement_month = round((retirement_age - current_age) * 12)
    total_months = round((end_age - current_age) * 12)
    
    # Compute first period length based on fractional age
    if current_age == int(current_age):
        first_period_months = 12
    else:
        first_period_months = round((1 - (current_age % 1)) * 12)
        
    results_by_age = {}
    
    for m in range(1, total_months + 1):
        # Determine period index for historical year assignment
        if m <= first_period_months:
            period_index = 0
        else:
            period_index = 1 + (m - first_period_months - 1) // 12
            
        if year_sequence is not None:
            # Monte Carlo mode: use pre-built random sequence of years
            if period_index >= len(year_sequence):
                break
            historical_year = year_sequence[period_index]
        else:
            # mean_stdev / historical_replay mode: simple increment from start_year
            historical_year = start_year + period_index
            if historical_year > last_data_year:
                break
            
        ret_pct = returns_by_year[historical_year] / 100.0
        monthly_rate = (1 + ret_pct) ** (1/12) - 1
        
        is_pre_retirement = m <= retirement_month
        age_this_month = current_age + (m - 1) / 12.0
        
        if is_pre_retirement:
            monthly_contrib_post = contrib_post_tax / 12.0
            monthly_contrib_pretax = contrib_pretax / 12.0
        else:
            years_elapsed = (m - 1) / 12.0
            annual_withdrawal = expenses * ((1 + inflation_rate) ** years_elapsed)
            monthly_withdrawal = annual_withdrawal / 12.0
            
        post_tax *= (1 + monthly_rate)
        pretax *= (1 + monthly_rate)
        
        # Handle one-time expenditures at this exact month
        for exp in expenditures:
            target_month = round((exp['age'] - current_age) * 12)
            if target_month == m:
                if exp.get('inflation_adjusted'):
                    elapsed_years = m / 12.0
                    exp_amount = exp['amount'] * ((1 + inflation_rate) ** elapsed_years)
                else:
                    exp_amount = exp['amount']
                
                if age_this_month < 59.5:
                    if post_tax >= exp_amount:
                        post_tax -= exp_amount
                    else:
                        shortfall = exp_amount - post_tax
                        post_tax = 0.0
                        if pretax >= shortfall:
                            pretax -= shortfall
                        else:
                            pretax = 0.0
                        if early_pretax_access_age is None:
                            early_pretax_access_age = age_this_month
                else:
                    pretax_withdrawal = exp_amount * (withdrawal_split_pretax_pct / 100.0)
                    posttax_withdrawal = exp_amount * (1.0 - withdrawal_split_pretax_pct / 100.0)
                    
                    if pretax >= pretax_withdrawal:
                        pretax -= pretax_withdrawal
                    else:
                        pretax_shortfall = pretax_withdrawal - pretax
                        pretax = 0.0
                        if post_tax >= pretax_shortfall:
                            post_tax -= pretax_shortfall
                        else:
                            pretax_shortfall -= post_tax
                            post_tax = 0.0
                            
                    if post_tax >= posttax_withdrawal:
                        post_tax -= posttax_withdrawal
                    else:
                        post_shortfall = posttax_withdrawal - post_tax
                        post_tax = 0.0
                        if pretax >= post_shortfall:
                            pretax -= post_shortfall
                        else:
                            pretax = 0.0
        
        # Handle recurring incomes
        if incomes:
            for inc in incomes:
                inc_start_month = round((inc['start_age'] - current_age) * 12)
                inc_end_month = round((inc['end_age'] - current_age) * 12)
                if inc_start_month <= m < inc_end_month:
                    monthly_inc = inc['amount'] / 12.0
                    if inc.get('inflation_adjusted'):
                        monthly_inc *= ((1 + inflation_rate) ** (m / 12.0))
                    post_tax += monthly_inc

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
                
                # Attempt pretax withdrawal
                if pretax >= pretax_withdrawal:
                    pretax -= pretax_withdrawal
                else:
                    pretax_shortfall = pretax_withdrawal - pretax
                    pretax = 0.0
                    if post_tax >= pretax_shortfall:
                        post_tax -= pretax_shortfall
                    else:
                        pretax_shortfall -= post_tax
                        post_tax = 0.0
                        
                # Attempt post_tax withdrawal
                if post_tax >= posttax_withdrawal:
                    post_tax -= posttax_withdrawal
                else:
                    post_shortfall = posttax_withdrawal - post_tax
                    post_tax = 0.0
                    if pretax >= post_shortfall:
                        pretax -= post_shortfall
                    else:
                        pretax = 0.0
                
        post_tax = max(0.0, post_tax)
        pretax = max(0.0, pretax)
        
        if m in target_months:
            target_age = target_months[m]
            results_by_age[target_age] = {
                "combined": post_tax + pretax,
                "post_tax": post_tax,
                "pretax": pretax
            }
            
    return results_by_age, early_pretax_access_age

def calculate_projection(scenario_data, accounts, annual_returns, expenditures=None, incomes=None):
    """
    Core projection calculation. Accepts scenario parameters, accounts, and returns as dicts/lists.
    Returns a result dict (with 'results', 'warning', 'early_access_warning') or an error dict.
    """
    if expenditures is None:
        expenditures = []
    if incomes is None:
        incomes = []
        
    current_age = float(scenario_data['current_age'])
    retirement_age = float(scenario_data['retirement_age'])
    end_age = int(scenario_data['end_age'])
    expenses = float(scenario_data['expected_expenses_in_retirement'])
    withdrawal_split_pretax_pct = float(scenario_data['withdrawal_split_pretax_pct'])
    inflation_rate = float(scenario_data['inflation_rate_pct']) / 100.0
    return_mode = scenario_data['return_mode']
    
    returns_by_year = {r['year']: r['return_pct'] for r in annual_returns}
    last_data_year = max(returns_by_year.keys())
    
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
        
    target_months = {round((A - current_age) * 12): A for A in target_ages}
    
    initial_post_tax = sum(a['current_balance'] for a in accounts if a['type'] == 'post-tax')
    initial_pretax = sum(a['current_balance'] for a in accounts if a['type'] == 'pre-tax')
    contrib_post_tax = sum(a['annual_contribution'] for a in accounts if a['type'] == 'post-tax')
    contrib_pretax = sum(a['annual_contribution'] for a in accounts if a['type'] == 'pre-tax')
    
    if return_mode == 'mean_stdev':
        start_year = int(scenario_data['return_start_year'])
        end_year = scenario_data.get('return_end_year')
        if end_year is not None:
            end_year = int(end_year)
        else:
            end_year = last_data_year
            
        if start_year > end_year:
            return {"error": "Return start year must be less than or equal to return end year."}
            
        eligible_years = [y for y in returns_by_year.keys() if start_year <= y <= end_year]
        if not eligible_years:
            return {"error": "No return data found in the selected year range."}
            
        results_by_age = {A: [] for A in target_ages}
        min_early_access_age = None
        early_access_count = 0
        total_simulations = len(eligible_years)
        
        for S in eligible_years:
            sim_results, early_age = _run_monthly_simulation(
                S, current_age, retirement_age, end_age, expenses, withdrawal_split_pretax_pct,
                inflation_rate, initial_post_tax, initial_pretax, contrib_post_tax, contrib_pretax,
                returns_by_year, last_data_year, target_months, expenditures, incomes
            )
            
            for target_age in target_ages:
                if target_age in sim_results:
                    results_by_age[target_age].append(sim_results[target_age])
                    
            if early_age is not None:
                early_access_count += 1
                if min_early_access_age is None or early_age < min_early_access_age:
                    min_early_access_age = early_age
                    
        final_results = []
        max_covered_age = None
        warning = None
        
        for target_age in target_ages:
            vals = results_by_age[target_age]
            if len(vals) < 5:
                break
                
            max_covered_age = target_age
            combined_vals = [v["combined"] for v in vals]
            post_tax_vals = [v["post_tax"] for v in vals]
            pretax_vals = [v["pretax"] for v in vals]
            
            mean = sum(combined_vals) / len(combined_vals)
            variance = sum((x - mean) ** 2 for x in combined_vals) / (len(combined_vals) - 1)
            stdev = math.sqrt(variance)
            
            mean_post_tax = sum(post_tax_vals) / len(post_tax_vals)
            mean_pretax = sum(pretax_vals) / len(pretax_vals)
            
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
            
        if max_covered_age is not None and max_covered_age < end_age:
            warning = f"Selected starting-year range doesn't cover the full projection horizon. Results shown only through age {max_covered_age}."
            
        early_access_warning = None
        if min_early_access_age is not None:
            pct = (early_access_count / total_simulations) * 100
            early_access_warning = f"In {early_access_count} out of {total_simulations} historical scenarios ({pct:.1f}%), pre-tax funds were accessed before age 59.5 because post-tax funds ran out, starting as early as age {min_early_access_age}."
            
        return {
            "results": final_results,
            "warning": warning,
            "early_access_warning": early_access_warning
        }
            
    elif return_mode == 'historical_replay':
        start_year = int(scenario_data['replay_start_year'])
        if start_year not in returns_by_year:
            return {"error": "Invalid replay start year."}
            
        sim_results, early_age = _run_monthly_simulation(
            start_year, current_age, retirement_age, end_age, expenses, withdrawal_split_pretax_pct,
            inflation_rate, initial_post_tax, initial_pretax, contrib_post_tax, contrib_pretax,
            returns_by_year, last_data_year, target_months, expenditures, incomes
        )
        
        final_results = []
        for target_age in target_ages:
            if target_age in sim_results:
                v = sim_results[target_age]
                final_results.append({
                    "age": target_age,
                    "mean_balance": v["combined"],
                    "mean_post_tax": v["post_tax"],
                    "mean_pretax": v["pretax"],
                    "stdev_balance": 0,
                    "ci50_low": v["combined"],
                    "ci50_high": v["combined"],
                    "ci70_low": v["combined"],
                    "ci70_high": v["combined"],
                    "ci95_low": v["combined"],
                    "ci95_high": v["combined"]
                })
                
        warning = None
        if len(final_results) > 0 and final_results[-1]["age"] < end_age:
            warning = "Historical data ran out before reaching end age."
            
        early_access_warning = None
        if early_age is not None:
            early_access_warning = f"In this historical scenario, pre-tax funds were accessed before age 59.5 because post-tax funds ran out, starting at age {early_age}."
            
        return {
            "results": final_results,
            "warning": warning,
            "early_access_warning": early_access_warning
        }
        
    elif return_mode == 'monte_carlo':
        start_year = int(scenario_data['return_start_year'])
        end_year = scenario_data.get('return_end_year')
        if end_year is not None:
            end_year = int(end_year)
        else:
            end_year = last_data_year
        block_length = int(scenario_data['block_length_years'])
        
        if block_length <= 0:
            return {"error": "Block length must be > 0."}
        if start_year > end_year:
            return {"error": "Return start year must be <= end year."}
            
        # Determine eligible block starting years
        sorted_years = sorted(returns_by_year.keys())
        eligible_starts = []
        for y in sorted_years:
            if y < start_year:
                continue
            if y + block_length - 1 > end_year:
                break
            block_years = range(y, y + block_length)
            if all(by in returns_by_year for by in block_years):
                eligible_starts.append(y)
                
        if not eligible_starts:
            return {"error": f"No valid blocks of length {block_length} exist within the selected year range ({start_year}-{end_year})."}
            
        total_months = round((end_age - current_age) * 12)
        horizon_years = math.ceil(total_months / 12)
        num_paths = 1000
        
        results_by_age = {A: [] for A in target_ages}
        depletion_counts = {A: 0 for A in target_ages}
        min_early_access_age = None
        early_access_count = 0
        
        for _ in range(num_paths):
            # Build one random path via block bootstrap
            path_years = []
            while len(path_years) < horizon_years:
                s = random.choice(eligible_starts)
                path_years.extend(range(s, s + block_length))
            path_years = path_years[:horizon_years]
            
            sim_results, early_age = _run_monthly_simulation(
                start_year, current_age, retirement_age, end_age, expenses, withdrawal_split_pretax_pct,
                inflation_rate, initial_post_tax, initial_pretax, contrib_post_tax, contrib_pretax,
                returns_by_year, last_data_year, target_months, expenditures, incomes, year_sequence=path_years
            )
            
            for target_age in target_ages:
                if target_age in sim_results:
                    results_by_age[target_age].append(sim_results[target_age])
                    # Track depletion: if combined balance is 0, it's depleted
                    if sim_results[target_age]["combined"] == 0.0:
                        depletion_counts[target_age] += 1
                        
            if early_age is not None:
                early_access_count += 1
                if min_early_access_age is None or early_age < min_early_access_age:
                    min_early_access_age = early_age
                    
        final_results = []
        for target_age in target_ages:
            vals = results_by_age[target_age]
            if not vals:
                break
                
            combined_vals = sorted([v["combined"] for v in vals])
            post_tax_vals = sorted([v["post_tax"] for v in vals])
            pretax_vals = sorted([v["pretax"] for v in vals])
            
            median_combined = _percentile(combined_vals, 50)
            median_post_tax = _percentile(post_tax_vals, 50)
            median_pretax = _percentile(pretax_vals, 50)
            
            ci50_low = _percentile(combined_vals, 25)
            ci50_high = _percentile(combined_vals, 75)
            ci70_low = _percentile(combined_vals, 15)
            ci70_high = _percentile(combined_vals, 85)
            ci95_low = _percentile(combined_vals, 2.5)
            ci95_high = _percentile(combined_vals, 97.5)
            
            depletion_pct = (depletion_counts[target_age] / num_paths) * 100
            
            final_results.append({
                "age": target_age,
                "mean_balance": median_combined,
                "mean_post_tax": median_post_tax,
                "mean_pretax": median_pretax,
                "stdev_balance": 0,
                "ci50_low": ci50_low,
                "ci50_high": ci50_high,
                "ci70_low": ci70_low,
                "ci70_high": ci70_high,
                "ci95_low": ci95_low,
                "ci95_high": ci95_high,
                "depletion_probability_pct": depletion_pct
            })
            
        early_access_warning = None
        if min_early_access_age is not None:
            pct = (early_access_count / num_paths) * 100
            early_access_warning = f"In {early_access_count} out of {num_paths} simulated paths ({pct:.1f}%), pre-tax funds were accessed before age 59.5 because post-tax funds ran out, starting as early as age {min_early_access_age}."
            
        return {
            "results": final_results,
            "warning": None,
            "early_access_warning": early_access_warning
        }
        
    else:
        return {"error": "Unsupported return mode."}

def run_projection(scenario_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    if not scenario:
        conn.close()
        return {"error": "Scenario not found"}, 404
        
    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()
    if not accounts:
        conn.close()
        return {"error": "No accounts found. Please add accounts before running a projection."}, 400
        
    cursor.execute("SELECT year, return_pct FROM annual_returns ORDER BY year")
    annual_returns = cursor.fetchall()
    if not annual_returns:
        conn.close()
        return {"error": "No annual return data found. Please upload historical returns."}, 400
        
    cursor.execute("SELECT amount, age, inflation_adjusted FROM scenario_expenditures WHERE scenario_id = ?", (scenario_id,))
    expenditures = [dict(e) for e in cursor.fetchall()]
        
    cursor.execute("SELECT start_age, end_age, amount, inflation_adjusted FROM scenario_incomes WHERE scenario_id = ?", (scenario_id,))
    incomes = [dict(i) for i in cursor.fetchall()]
        
    conn.close()
    
    result = calculate_projection(dict(scenario), [dict(a) for a in accounts], [dict(r) for r in annual_returns], expenditures, incomes)
    if "error" in result:
        return result, 400
    return result
