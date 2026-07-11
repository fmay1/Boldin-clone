import math
from database import get_connection

def run_projection(scenario_id):
    """
    Runs a year-by-year projection for a given scenario.
    Currently supports only 'mean_stdev' return mode.
    Returns a dictionary with year-by-year results and metadata.
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
    
    # Only mean/stdev mode is implemented in Step 5
    if return_mode != 'mean_stdev':
        return {"error": "Only mean_stdev mode is currently supported."}, 400
        
    start_year = scenario['return_start_year']
    end_year = scenario['return_end_year']
    
    # Calculate mean and stdev from selected range
    returns_in_range = [r['return_pct'] for r in annual_returns if start_year <= r['year'] <= end_year]
    if not returns_in_range:
        return {"error": "No return data found in the selected year range."}, 400
        
    mean_return = sum(returns_in_range) / len(returns_in_range)
    variance = sum((x - mean_return) ** 2 for x in returns_in_range) / len(returns_in_range)
    stdev_return = math.sqrt(variance)
    
    mean_return_rate = mean_return / 100.0
    stdev_return_rate = stdev_return / 100.0
    
    # Initialize projection results
    results = []
    depleted_at_age = None
    
    # Current balances for main, low, and high confidence bands
    # Each is a list of account balances
    main_balances = [a['current_balance'] for a in accounts]
    low_balances = [a['current_balance'] for a in accounts]
    high_balances = [a['current_balance'] for a in accounts]
    
    contributions = [a['annual_contribution'] for a in accounts]
    account_types = [a['type'] for a in accounts]
    
    for age in range(current_age, end_age + 1):
        years_since_start = age - current_age
        
        # Inflation-adjusted expenses
        annual_expenses = expenses * ((1 + inflation_rate) ** years_since_start)
        
        # Apply contributions if pre-retirement
        if age < retirement_age:
            for i in range(len(accounts)):
                main_balances[i] += contributions[i]
                low_balances[i] += contributions[i]
                high_balances[i] += contributions[i]
                
        # Apply withdrawals if post-retirement
        if age >= retirement_age:
            if depleted_at_age is None:
                # Determine withdrawal split
                if age < 59.5:
                    pretax_pct = 0.0
                    posttax_pct = 1.0
                else:
                    pretax_pct = withdrawal_split_pretax_pct / 100.0
                    posttax_pct = 1.0 - pretax_pct
                    
                pretax_withdrawal = annual_expenses * pretax_pct
                posttax_withdrawal = annual_expenses * posttax_pct
                
                # Withdraw from main balances
                _apply_withdrawals(main_balances, account_types, pretax_withdrawal, posttax_withdrawal)
                _apply_withdrawals(low_balances, account_types, pretax_withdrawal, posttax_withdrawal)
                _apply_withdrawals(high_balances, account_types, pretax_withdrawal, posttax_withdrawal)
                
        # Apply returns
        for i in range(len(accounts)):
            main_balances[i] *= (1 + mean_return_rate)
            low_balances[i] *= (1 + mean_return_rate - stdev_return_rate)
            high_balances[i] *= (1 + mean_return_rate + stdev_return_rate)
            
        # Floor at zero
        for i in range(len(accounts)):
            main_balances[i] = max(0, main_balances[i])
            low_balances[i] = max(0, low_balances[i])
            high_balances[i] = max(0, high_balances[i])
            
        # Check for depletion
        total_main = sum(main_balances)
        if total_main == 0 and depleted_at_age is None:
            depleted_at_age = age
            
        # Record results
        results.append({
            "age": age,
            "main_balance": total_main,
            "low_balance": sum(low_balances),
            "high_balance": sum(high_balances),
            "post_tax_balance": sum(main_balances[i] for i in range(len(accounts)) if account_types[i] == 'post-tax'),
            "pre_tax_balance": sum(main_balances[i] for i in range(len(accounts)) if account_types[i] == 'pre-tax')
        })
        
    return {
        "results": results,
        "depleted_at_age": depleted_at_age,
        "mean_return": mean_return,
        "stdev_return": stdev_return
    }

def _apply_withdrawals(balances, account_types, pretax_withdrawal, posttax_withdrawal):
    """
    Applies withdrawals to account balances based on pre/post-tax split.
    If one account type runs out, the shortfall is covered by the other type.
    """
    remaining_pretax = pretax_withdrawal
    remaining_posttax = posttax_withdrawal
    
    # First pass: withdraw from designated types
    for i in range(len(balances)):
        if account_types[i] == 'pre-tax' and remaining_pretax > 0:
            withdrawal = min(remaining_pretax, balances[i])
            balances[i] -= withdrawal
            remaining_pretax -= withdrawal
        elif account_types[i] == 'post-tax' and remaining_posttax > 0:
            withdrawal = min(remaining_posttax, balances[i])
            balances[i] -= withdrawal
            remaining_posttax -= withdrawal
            
    # Second pass: cover shortfall from the other type
    if remaining_pretax > 0:
        for i in range(len(balances)):
            if account_types[i] == 'post-tax' and remaining_pretax > 0:
                withdrawal = min(remaining_pretax, balances[i])
                balances[i] -= withdrawal
                remaining_pretax -= withdrawal
                
    if remaining_posttax > 0:
        for i in range(len(balances)):
            if account_types[i] == 'pre-tax' and remaining_posttax > 0:
                withdrawal = min(remaining_posttax, balances[i])
                balances[i] -= withdrawal
                remaining_posttax -= withdrawal
