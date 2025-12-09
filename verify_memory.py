import sys
import argparse
from orchestration.memory import memory_system

USER_ID = "persistence_tester"
MEMORY_TEXT = "My favorite color is #00FF00"

def setup():
    print(f"Saving memory for {USER_ID}: '{MEMORY_TEXT}'")
    # memory_system is initialized on import, which loads the persistent DB
    memory_system.save_memory(USER_ID, MEMORY_TEXT, "user", "phase_1")
    print("Memory saved. Exiting.")

def check():
    print(f"Retrieving memory for {USER_ID}...")
    # memory_system re-initialized (simulating new session)
    memories = memory_system.retrieve_memory(USER_ID, "favorite color")
    found = any(MEMORY_TEXT in m.text for m in memories)
    
    if found:
        print("SUCCESS: Memory persisted across sessions!")
        for m in memories:
            print(f" - Found: {m.text} (metadata: {m.metadata})")
    else:
        print("FAILURE: Memory not found.")
        print(f"Retrieved: {[m.text for m in memories]}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.setup:
        setup()
    elif args.check:
        check()
    else:
        print("Use --setup or --check")
