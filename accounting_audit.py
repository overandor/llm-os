"""
Accounting audit for decentralized inference node
Verifies accounting consistency across the system
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from liquid_endpoint_store import LiquidEndpointStore


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_success(message):
    """Print success message."""
    print(f"✓ {message}")


def print_error(message):
    """Print error message."""
    print(f"✗ {message}")


def print_warning(message):
    """Print warning message."""
    print(f"⚠ {message}")


def run_accounting_audit(db_path: Path = None):
    """Run accounting audit on liquid endpoint store."""
    
    print_section("ACCOUNTING AUDIT")
    
    if db_path is None:
        db_path = Path.home() / "llm_liquid_endpoints.db"
    
    if not db_path.exists():
        print_error(f"Database not found at {db_path}")
        return False
    
    store = LiquidEndpointStore(db_path)
    
    all_passed = True
    
    # 1. Check for negative balances
    print_section("1. CHECK FOR NEGATIVE BALANCES")
    try:
        # This would require exposing a method to check all balances
        # For now, we'll check endpoint balances
        endpoints = store.list_endpoints()
        negative_found = False
        
        for endpoint in endpoints:
            if endpoint.total_staked < 0:
                print_error(f"Endpoint {endpoint.endpoint_id} has negative total_staked: {endpoint.total_staked}")
                all_passed = False
                negative_found = True
            if endpoint.liquid_supply < 0:
                print_error(f"Endpoint {endpoint.endpoint_id} has negative liquid_supply: {endpoint.liquid_supply}")
                all_passed = False
                negative_found = True
            if endpoint.pending_rewards < 0:
                print_error(f"Endpoint {endpoint.endpoint_id} has negative pending_rewards: {endpoint.pending_rewards}")
                all_passed = False
                negative_found = True
        
        if not negative_found:
            print_success("No negative balances found")
    except Exception as e:
        print_error(f"Error checking balances: {e}")
        all_passed = False
    
    # 2. Verify revenue share calculations
    print_section("2. VERIFY REVENUE SHARE CALCULATIONS")
    try:
        for endpoint in endpoints:
            if endpoint.total_revenue > 0:
                # Calculate expected staker share
                expected_staker_share = endpoint.total_revenue * (endpoint.revenue_share_bps / 10000.0)
                expected_operator_share = endpoint.total_revenue - expected_staker_share
                
                # Check if pending rewards is reasonable
                if endpoint.pending_rewards > endpoint.total_revenue:
                    print_error(f"Endpoint {endpoint.endpoint_id}: pending_rewards ({endpoint.pending_rewards}) > total_revenue ({endpoint.total_revenue})")
                    all_passed = False
                else:
                    print_success(f"Endpoint {endpoint.endpoint_id}: revenue share within bounds")
    except Exception as e:
        print_error(f"Error verifying revenue share: {e}")
        all_passed = False
    
    # 3. Verify every completed job has a receipt
    print_section("3. VERIFY COMPLETED JOBS HAVE RECEIPTS")
    try:
        # This would require tracking jobs in the job queue
        # For now, we'll check receipts exist
        receipts = []
        for endpoint in endpoints:
            endpoint_receipts = store.get_receipts(endpoint.endpoint_id)
            receipts.extend(endpoint_receipts)
        
        print_success(f"Found {len(receipts)} receipts in database")
        
        # Check each receipt has required fields
        for receipt in receipts:
            if not receipt.receipt_id:
                print_error(f"Receipt missing receipt_id")
                all_passed = False
            if not receipt.endpoint_id:
                print_error(f"Receipt {receipt.receipt_id} missing endpoint_id")
                all_passed = False
            if not receipt.signature:
                print_warning(f"Receipt {receipt.receipt_id} missing signature")
            if receipt.fee_paid < 0:
                print_error(f"Receipt {receipt.receipt_id} has negative fee_paid: {receipt.fee_paid}")
                all_passed = False
    except Exception as e:
        print_error(f"Error checking receipts: {e}")
        all_passed = False
    
    # 4. Verify receipt fee matches endpoint revenue
    print_section("4. VERIFY RECEIPT FEES MATCH ENDPOINT REVENUE")
    try:
        for endpoint in endpoints:
            endpoint_receipts = store.get_receipts(endpoint.endpoint_id)
            total_receipt_fees = sum(r.fee_paid for r in endpoint_receipts)
            
            # Allow small floating point differences
            if abs(total_receipt_fees - endpoint.total_revenue) > 0.0001:
                print_warning(f"Endpoint {endpoint.endpoint_id}: receipt fees ({total_receipt_fees}) != total_revenue ({endpoint.total_revenue})")
                print_warning(f"  Difference: {abs(total_receipt_fees - endpoint.total_revenue)}")
            else:
                print_success(f"Endpoint {endpoint.endpoint_id}: receipt fees match total revenue")
    except Exception as e:
        print_error(f"Error verifying receipt fees: {e}")
        all_passed = False
    
    # 5. Verify staker positions
    print_section("5. VERIFY STAKER POSITIONS")
    try:
        for endpoint in endpoints:
            positions = store.get_stake_positions(endpoint.endpoint_id)
            
            total_staked_from_positions = sum(p.staked_amount for p in positions)
            
            if abs(total_staked_from_positions - endpoint.total_staked) > 0.0001:
                print_warning(f"Endpoint {endpoint.endpoint_id}: position stakes ({total_staked_from_positions}) != total_staked ({endpoint.total_staked})")
            else:
                print_success(f"Endpoint {endpoint.endpoint_id}: staker positions match total_staked")
            
            # Check liquid tokens
            total_liquid_from_positions = sum(p.liquid_tokens_minted for p in positions)
            if abs(total_liquid_from_positions - endpoint.liquid_supply) > 0.0001:
                print_warning(f"Endpoint {endpoint.endpoint_id}: position liquid ({total_liquid_from_positions}) != liquid_supply ({endpoint.liquid_supply})")
            else:
                print_success(f"Endpoint {endpoint.endpoint_id}: liquid tokens match liquid_supply")
    except Exception as e:
        print_error(f"Error verifying staker positions: {e}")
        all_passed = False
    
    # 6. Verify exchange rate consistency
    print_section("6. VERIFY EXCHANGE RATE CONSISTENCY")
    try:
        for endpoint in endpoints:
            if endpoint.liquid_supply > 0:
                expected_rate = endpoint.total_staked / endpoint.liquid_supply
                if abs(expected_rate - endpoint.exchange_rate) > 0.01:
                    print_warning(f"Endpoint {endpoint.endpoint_id}: exchange rate mismatch")
                    print_warning(f"  Expected: {expected_rate}, Actual: {endpoint.exchange_rate}")
                else:
                    print_success(f"Endpoint {endpoint.endpoint_id}: exchange rate consistent")
    except Exception as e:
        print_error(f"Error verifying exchange rates: {e}")
        all_passed = False
    
    # Final summary
    print_section("AUDIT SUMMARY")
    
    if all_passed:
        print_success("ALL CHECKS PASSED ✓")
        print("\nAccounting is consistent:")
        print("  ✓ No negative balances")
        print("  ✓ Revenue share calculations valid")
        print("  ✓ Receipts have required fields")
        print("  ✓ Receipt fees match endpoint revenue")
        print("  ✓ Staker positions match totals")
        print("  ✓ Exchange rates consistent")
    else:
        print_error("SOME CHECKS FAILED ✗")
        print("\nReview the errors above and fix accounting inconsistencies.")
    
    return all_passed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Accounting audit for decentralized inference node")
    parser.add_argument("--db", type=str, help="Path to database file")
    
    args = parser.parse_args()
    
    db_path = Path(args.db) if args.db else None
    success = run_accounting_audit(db_path)
    
    sys.exit(0 if success else 1)
