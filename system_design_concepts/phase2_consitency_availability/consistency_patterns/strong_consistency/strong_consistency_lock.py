# strong_consistency_lock.py - Two-Phase Commit for distributed transaction
import time
import threading
import random
from enum import Enum

class TransactionState(Enum):
    PREPARE = 1
    COMMIT = 2
    ABORT = 3

class DatabaseNode:
    """Simulates a database node participating in 2PC"""
    
    def __init__(self, node_id, fail_probability=0.0):
        self.node_id = node_id
        self.fail_probability = fail_probability
        self.prepared_transactions = {}
        self.lock = threading.Lock()
    
    def prepare(self, transaction_id, operation):
        """Phase 1: Can you commit this transaction?"""
        
        # Simulate random failure
        if random.random() < self.fail_probability:
            print(f"  [{self.node_id}] ❌ VOTE-NO (simulated failure)")
            return "NO"
        
        with self.lock:
            # Check if we can perform this operation
            # (In real system: check constraints, locks, etc.)
            
            # Store prepared transaction
            self.prepared_transactions[transaction_id] = operation
            
            print(f"  [{self.node_id}] ✓ VOTE-YES (prepared)")
            return "YES"
    
    def commit(self, transaction_id):
        """Phase 2: Commit the transaction"""
        with self.lock:
            if transaction_id in self.prepared_transactions:
                operation = self.prepared_transactions[transaction_id]
                # Actually perform the operation
                print(f"  [{self.node_id}] ✓ COMMITTED: {operation}")
                del self.prepared_transactions[transaction_id]
                return True
            return False
    
    def abort(self, transaction_id):
        """Phase 2: Abort the transaction"""
        with self.lock:
            if transaction_id in self.prepared_transactions:
                print(f"  [{self.node_id}] ✗ ABORTED")
                del self.prepared_transactions[transaction_id]
                return True
            return False


class TwoPhaseCommitCoordinator:
    """Coordinator for 2PC protocol (ensures strong consistency)"""
    
    def __init__(self, nodes):
        self.nodes = nodes
        self.transaction_id = 0
    
    def execute_transaction(self, operations):
        """
        Execute distributed transaction with strong consistency.
        All nodes commit, or all nodes abort (atomic).
        """
        self.transaction_id += 1
        tid = self.transaction_id
        
        print(f"\n{'='*60}")
        print(f"Transaction {tid}: {operations}")
        print(f"{'='*60}")
        
        # PHASE 1: PREPARE
        print(f"\n[PHASE 1] Coordinator sends PREPARE to all nodes")
        prepare_votes = []
        
        for i, node in enumerate(self.nodes):
            vote = node.prepare(tid, operations[i])
            prepare_votes.append(vote)
            time.sleep(0.1)  # Simulate network delay
        
        print(f"\n[PHASE 1] Votes received: {prepare_votes}")
        
        # Decision: ALL must vote YES
        if all(vote == "YES" for vote in prepare_votes):
            # PHASE 2: COMMIT
            print(f"\n[PHASE 2] All voted YES → Coordinator sends COMMIT")
            
            for node in self.nodes:
                node.commit(tid)
                time.sleep(0.1)
            
            print(f"\n✅ Transaction {tid} COMMITTED on all nodes")
            print("   Strong consistency maintained: all nodes have same state")
            return "COMMITTED"
        
        else:
            # PHASE 2: ABORT
            print(f"\n[PHASE 2] At least one voted NO → Coordinator sends ABORT")
            
            for node in self.nodes:
                node.abort(tid)
                time.sleep(0.1)
            
            print(f"\n❌ Transaction {tid} ABORTED on all nodes")
            print("   Strong consistency maintained: no partial commits")
            return "ABORTED"


# Demo: Strong consistency with 2PC
def demo_strong_consistency():
    print("=== Strong Consistency with Two-Phase Commit ===\n")
    
    # Create 3 database nodes
    db1 = DatabaseNode("DB-1")
    db2 = DatabaseNode("DB-2")
    db3 = DatabaseNode("DB-3")
    
    coordinator = TwoPhaseCommitCoordinator([db1, db2, db3])
    
    # Transaction 1: All nodes healthy (SUCCESS)
    print("\n" + "="*60)
    print("SCENARIO 1: All nodes healthy")
    print("="*60)
    
    coordinator.execute_transaction([
        "INSERT user_id=123 INTO users",
        "INSERT user_id=123 INTO profiles", 
        "INSERT user_id=123 INTO permissions"
    ])
    
    time.sleep(1)
    
    # Transaction 2: One node fails (ALL ABORT)
    print("\n\n" + "="*60)
    print("SCENARIO 2: One node fails during PREPARE")
    print("="*60)
    
    # Make DB-2 fail
    db2.fail_probability = 1.0
    
    coordinator.execute_transaction([
        "INSERT user_id=456 INTO users",
        "INSERT user_id=456 INTO profiles",
        "INSERT user_id=456 INTO permissions"
    ])
    
    print("\n" + "="*60)
    print("KEY INSIGHT:")
    print("="*60)
    print("With strong consistency (2PC):")
    print("  • Either ALL nodes commit, or ALL nodes abort")
    print("  • No partial state (no inconsistency)")
    print("  • Trade-off: Lower availability (one node down = all fail)")
    print("  • Perfect for: Banking, inventory, critical transactions")

if __name__ == '__main__':
    demo_strong_consistency()