"""
Worker Entry Point

Run with: python -m worker.run_worker 1
"""
import asyncio
import sys

# Make sure parent directory is in path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.bid_worker import main

if __name__ == "__main__":
    asyncio.run(main())