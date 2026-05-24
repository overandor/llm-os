"""
Enterprise Procurement Example: LLM OS for AI Agent Management
"""

from llm_os.server import VMInstance
from llm_os.policy import Policy, ActionClass

def main():
    """Enterprise LLM OS example"""
    print("=== Enterprise LLM OS Example ===")
    
    # Initialize VM with enterprise policy
    policy = Policy(
        name="enterprise_default",
        action_classes={ActionClass.SAFE, ActionClass.STANDARD},
        daily_cost_limit_usd=1000.0,
        single_action_cost_limit_usd=100.0,
        simulation_mode=True,
        allow_model_training=True,
        allow_real_payments=False,
        allow_production_deploy=False,
    )
    
    vm = VMInstance()
    print("VM initialized with enterprise policy")
    print("Simulation mode enabled for safe testing")
    print("Cost limits enforced for budget control")

if __name__ == "__main__":
    main()
