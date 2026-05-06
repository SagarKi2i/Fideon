import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.nl_summary import generate_nl_summary

async def main():
    # Mock extracted data
    extracted = {
        "document_identification": {
            "document_type": "CERTIFICATE OF LIABILITY INSURANCE",
            "form_number": "ACORD 25",
            "edition_date": "2016/03"
        },
        "parties": {
            "named_insured": {"value": "John Doe Construction Inc"},
            "insurer": {"value": "Hartford Insurance"},
            "agency": {"value": "Elite Brokers"}
        },
        "policy_identifiers": {
            "policy_number": {"value": "GL-12345678"}
        },
        "dates": {
            "effective_date": {"value": "2024-01-01"},
            "expiration_date": {"value": "2025-01-01"}
        },
        "coverages": [
            {
                "coverage_name": "General Liability",
                "limit": "$1,000,000",
                "deductible": "$500"
            }
        ]
    }
    
    raw_text = "This is a certificate of liability insurance for John Doe Construction Inc. Policy GL-12345678 is active from 2024-01-01 to 2025-01-01."
    
    print("Testing generate_nl_summary...")
    summary = await generate_nl_summary(extracted, raw_text)
    
    if summary:
        print("\nSUCCESS! Summary generated:")
        print("-" * 40)
        print(summary)
        print("-" * 40)
    else:
        print("\nFAILED: No summary generated. This could be because:")
        print("1. ACORD_NL_SUMMARY_ENABLED is false")
        print("2. LLM endpoint is unreachable")
        print("3. LLM failed to generate text")
        
        # Debugging info
        enabled = os.getenv("ACORD_NL_SUMMARY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        print(f"\nDebug Info:")
        print(f"ACORD_NL_SUMMARY_ENABLED: {enabled}")
        print(f"RUNPOD_GENERATE_URL: {os.getenv('RUNPOD_GENERATE_URL')}")
        print(f"OFFLINE_LLM_GENERATE_URL: {os.getenv('OFFLINE_LLM_GENERATE_URL')}")

if __name__ == "__main__":
    asyncio.run(main())
