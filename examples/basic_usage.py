#!/usr/bin/env python3
"""
Example usage of the Politia system
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from politia.api.client import APIClient


def main():
    """Example of using the Politia API client"""
    print("Politia System - Basic Usage Example\n")
    
    # Initialize API client (assumes API is running)
    client = APIClient()
    
    # Example 1: Search for a person
    print("1. Searching for persons named 'Meloni'...")
    persons = client.search_persons("Meloni", limit=5)
    print(f"   Found {len(persons)} persons")
    for person in persons[:3]:
        print(f"   - {person.get('full_name')} ({person.get('party')})")
    
    # Example 2: Search speeches
    print("\n2. Searching speeches about 'clima'...")
    speeches = client.search_speeches(search_text="clima", limit=5)
    print(f"   Found {len(speeches)} speeches")
    for speech in speeches[:3]:
        speaker = speech.get('speaker_id', 'Unknown')
        text_preview = speech.get('text', '')[:100]
        print(f"   - Speaker: {speaker}")
        print(f"     Text: {text_preview}...")
    
    # Example 3: Search topics
    print("\n3. Searching topics about 'mozione'...")
    topics = client.search_topics("mozione", limit=5)
    print(f"   Found {len(topics)} topics")
    for topic in topics[:3]:
        print(f"   - {topic.get('title')}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()


