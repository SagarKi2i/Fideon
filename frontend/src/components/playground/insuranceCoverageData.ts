// Comprehensive insurance coverage data for each insurance type

export interface CoverageItem {
  name: string;
  limit: string;
  description: string;
}

export interface CoverageSection {
  title: string;
  icon: string;
  items: CoverageItem[];
}

export interface InsuranceCoverageConfig {
  sections: CoverageSection[];
  exclusions: string[];
  conditions: string[];
}

export const INSURANCE_COVERAGE_DATA: Record<string, InsuranceCoverageConfig> = {
  auto: {
    sections: [
      {
        title: "Liability Coverage",
        icon: "shield",
        items: [
          { name: "Bodily Injury Liability", limit: "$100,000 / $300,000", description: "Per person / Per accident for injuries you cause to others" },
          { name: "Property Damage Liability", limit: "$100,000", description: "Damage you cause to other people's property" },
          { name: "Combined Single Limit (CSL)", limit: "$500,000", description: "Total liability coverage per accident" },
        ]
      },
      {
        title: "Medical Payments",
        icon: "heart",
        items: [
          { name: "Medical Payments Coverage", limit: "$10,000", description: "Per person for medical expenses regardless of fault" },
          { name: "Personal Injury Protection (PIP)", limit: "$25,000", description: "Medical, lost wages, and essential services" },
        ]
      },
      {
        title: "Uninsured/Underinsured Motorist",
        icon: "car",
        items: [
          { name: "UM Bodily Injury", limit: "$100,000 / $300,000", description: "Protection if hit by uninsured driver" },
          { name: "UM Property Damage", limit: "$50,000", description: "Property damage from uninsured driver" },
          { name: "UIM Coverage", limit: "$100,000 / $300,000", description: "Coverage gap from underinsured drivers" },
        ]
      },
      {
        title: "Physical Damage",
        icon: "wrench",
        items: [
          { name: "Collision Coverage", limit: "Actual Cash Value", description: "Damage from collision with another vehicle or object" },
          { name: "Comprehensive Coverage", limit: "Actual Cash Value", description: "Theft, vandalism, weather, fire, animals" },
          { name: "Rental Reimbursement", limit: "$50/day, 30 days max", description: "Rental car while yours is being repaired" },
          { name: "Towing & Labor", limit: "$100 per occurrence", description: "Roadside assistance and towing" },
        ]
      }
    ],
    exclusions: [
      "Racing or speed contests",
      "Intentional damage",
      "Commercial use (unless endorsed)",
      "Vehicles not listed on policy",
      "Mechanical breakdown",
      "Wear and tear"
    ],
    conditions: [
      "Coverage applies to listed drivers only",
      "Policy territory: United States and Canada",
      "30-day notice required for cancellation",
      "Premium based on driving record and vehicle"
    ]
  },
  home: {
    sections: [
      {
        title: "Dwelling Coverage (Coverage A)",
        icon: "home",
        items: [
          { name: "Dwelling Protection", limit: "$500,000", description: "Structure of your home and attached structures" },
          { name: "Extended Replacement Cost", limit: "125% of Coverage A", description: "Additional coverage if rebuilding costs exceed limit" },
          { name: "Building Code Upgrade", limit: "10% of Coverage A", description: "Bring home up to current building codes" },
        ]
      },
      {
        title: "Other Structures (Coverage B)",
        icon: "building",
        items: [
          { name: "Detached Structures", limit: "10% of Coverage A", description: "Garages, sheds, fences, guest houses" },
          { name: "Other Structures Increased", limit: "Up to 20% of Coverage A", description: "Optional increased limits available" },
        ]
      },
      {
        title: "Personal Property (Coverage C)",
        icon: "package",
        items: [
          { name: "Personal Belongings", limit: "70% of Coverage A", description: "Furniture, electronics, clothing, etc." },
          { name: "Special Limits - Jewelry", limit: "$5,000", description: "Watches, gems, furs (schedulable)" },
          { name: "Special Limits - Electronics", limit: "$10,000", description: "Computers, cameras, equipment" },
          { name: "Special Limits - Cash/Securities", limit: "$1,500", description: "Money, coins, gold, silver" },
          { name: "Off-Premises Coverage", limit: "10% of Coverage C", description: "Personal property away from home" },
        ]
      },
      {
        title: "Loss of Use (Coverage D)",
        icon: "clock",
        items: [
          { name: "Additional Living Expenses", limit: "30% of Coverage A", description: "Hotel, meals, temporary housing" },
          { name: "Fair Rental Value", limit: "$3,000/month", description: "Lost rental income if applicable" },
          { name: "Civil Authority Coverage", limit: "2 weeks", description: "Evacuation ordered by authorities" },
        ]
      },
      {
        title: "Liability Coverage (Coverage E)",
        icon: "shield",
        items: [
          { name: "Personal Liability", limit: "$300,000", description: "Bodily injury/property damage to others" },
          { name: "Premises Liability", limit: "$300,000", description: "Injuries occurring on your property" },
          { name: "Host Liquor Liability", limit: "Included", description: "Social host protection" },
        ]
      },
      {
        title: "Medical Payments (Coverage F)",
        icon: "heart",
        items: [
          { name: "Medical Payments to Others", limit: "$5,000 per person", description: "Medical expenses for guests injured on premises" },
        ]
      }
    ],
    exclusions: [
      "Flood damage (separate policy required)",
      "Earthquake damage (endorsement available)",
      "Neglect or intentional loss",
      "War or nuclear hazard",
      "Government action",
      "Power failure originating off premises",
      "Earth movement",
      "Water backup (endorsement available)"
    ],
    conditions: [
      "Replacement cost coverage on dwelling",
      "Annual policy with monthly payment option",
      "Claim-free discount applied",
      "Protective devices credit included"
    ]
  },
  commercial: {
    sections: [
      {
        title: "Building Coverage",
        icon: "building",
        items: [
          { name: "Building/Structure", limit: "$2,000,000", description: "Commercial building and fixtures" },
          { name: "Tenant Improvements", limit: "$250,000", description: "Improvements made to leased space" },
          { name: "Outdoor Signs", limit: "$25,000", description: "Business signage coverage" },
          { name: "Glass Coverage", limit: "$10,000", description: "Plate glass and storefront windows" },
        ]
      },
      {
        title: "Business Personal Property",
        icon: "package",
        items: [
          { name: "Contents & Equipment", limit: "$500,000", description: "Furniture, machinery, inventory" },
          { name: "Electronic Data Processing", limit: "$100,000", description: "Computers, software, data" },
          { name: "Valuable Papers", limit: "$50,000", description: "Important documents and records" },
          { name: "Property in Transit", limit: "$25,000", description: "Property being transported" },
          { name: "Accounts Receivable", limit: "$100,000", description: "Uncollectible accounts due to loss" },
        ]
      },
      {
        title: "Business Income",
        icon: "dollar",
        items: [
          { name: "Business Income Coverage", limit: "$500,000 / 12 months", description: "Lost income during restoration" },
          { name: "Extra Expense", limit: "$100,000", description: "Additional costs to continue operations" },
          { name: "Extended Business Income", limit: "60 days", description: "Income loss after restoration" },
          { name: "Civil Authority", limit: "30 days", description: "Access prohibited by authorities" },
          { name: "Dependent Properties", limit: "$50,000", description: "Suppliers/customers affected" },
        ]
      },
      {
        title: "Additional Coverages",
        icon: "plus",
        items: [
          { name: "Spoilage Coverage", limit: "$50,000", description: "Perishable goods (if applicable)" },
          { name: "Equipment Breakdown", limit: "$250,000", description: "Mechanical/electrical breakdown" },
          { name: "Debris Removal", limit: "25% of loss", description: "Cleanup after covered loss" },
          { name: "Ordinance or Law", limit: "$100,000", description: "Building code compliance costs" },
        ]
      }
    ],
    exclusions: [
      "Flood and earthquake (separate policies)",
      "Employee dishonesty (crime policy)",
      "Professional errors (E&O policy)",
      "Pollution and contamination",
      "Cyber incidents (cyber policy)",
      "War and terrorism",
      "Nuclear hazard"
    ],
    conditions: [
      "Actual Cash Value or Replacement Cost basis",
      "80% Coinsurance requirement",
      "Annual policy term",
      "Loss payee endorsements available"
    ]
  },
  "general-liability": {
    sections: [
      {
        title: "Commercial General Liability",
        icon: "shield",
        items: [
          { name: "General Aggregate Limit", limit: "$2,000,000", description: "Maximum policy will pay per policy period" },
          { name: "Products-Completed Ops Aggregate", limit: "$2,000,000", description: "Products and completed operations" },
          { name: "Each Occurrence Limit", limit: "$1,000,000", description: "Maximum per occurrence" },
          { name: "Personal & Advertising Injury", limit: "$1,000,000", description: "Libel, slander, copyright infringement" },
          { name: "Damage to Rented Premises", limit: "$300,000", description: "Fire damage to rented premises" },
          { name: "Medical Expense Limit", limit: "$10,000", description: "Per person medical payments" },
        ]
      },
      {
        title: "Premises & Operations",
        icon: "building",
        items: [
          { name: "Premises Liability", limit: "Per Occurrence Limit", description: "Injuries on your premises" },
          { name: "Operations Liability", limit: "Per Occurrence Limit", description: "Injuries from your operations" },
          { name: "Completed Operations", limit: "Aggregate Limit", description: "Liability after work is done" },
        ]
      },
      {
        title: "Products Liability",
        icon: "package",
        items: [
          { name: "Products Liability", limit: "$2,000,000 aggregate", description: "Products you manufacture or sell" },
          { name: "Recall Expense", limit: "$50,000", description: "Product recall costs (if endorsed)" },
        ]
      },
      {
        title: "Additional Coverages",
        icon: "plus",
        items: [
          { name: "Blanket Additional Insured", limit: "Included", description: "Automatic additional insured status" },
          { name: "Waiver of Subrogation", limit: "Included", description: "Waive recovery rights when required" },
          { name: "Primary & Non-Contributory", limit: "Included", description: "Your policy pays first" },
          { name: "Per Project Aggregate", limit: "Available", description: "Separate aggregate per project" },
        ]
      }
    ],
    exclusions: [
      "Workers compensation claims",
      "Professional services errors",
      "Pollution and contamination",
      "Auto liability (separate policy)",
      "Employment practices liability",
      "Cyber liability",
      "Intentional acts"
    ],
    conditions: [
      "Occurrence form coverage",
      "Defense costs outside limits",
      "Worldwide coverage territory",
      "Additional insured endorsements available"
    ]
  },
  "workers-comp": {
    sections: [
      {
        title: "Workers Compensation (Part One)",
        icon: "users",
        items: [
          { name: "Statutory Benefits", limit: "Statutory", description: "As required by state law" },
          { name: "Medical Benefits", limit: "Unlimited", description: "All reasonable medical expenses" },
          { name: "Temporary Total Disability", limit: "66.67% of wages", description: "Weekly benefits during recovery" },
          { name: "Permanent Partial Disability", limit: "Per schedule", description: "Benefits for permanent impairment" },
          { name: "Permanent Total Disability", limit: "Lifetime benefits", description: "Complete inability to work" },
          { name: "Death Benefits", limit: "Statutory", description: "Benefits to dependents" },
        ]
      },
      {
        title: "Employers Liability (Part Two)",
        icon: "briefcase",
        items: [
          { name: "Bodily Injury by Accident", limit: "$1,000,000", description: "Each accident limit" },
          { name: "Bodily Injury by Disease", limit: "$1,000,000", description: "Policy limit for disease" },
          { name: "Bodily Injury by Disease", limit: "$1,000,000", description: "Each employee limit" },
        ]
      },
      {
        title: "Additional Benefits",
        icon: "heart",
        items: [
          { name: "Rehabilitation Services", limit: "Included", description: "Vocational rehabilitation" },
          { name: "Supplemental Benefits", limit: "Per state", description: "Additional state-mandated benefits" },
          { name: "Second Injury Fund", limit: "Available", description: "Pre-existing condition protection" },
        ]
      }
    ],
    exclusions: [
      "Intentional self-injury",
      "Intoxication or drug use",
      "Independent contractors",
      "Domestic employees (varies by state)",
      "Farm workers (varies by state)",
      "Willful violation of safety rules"
    ],
    conditions: [
      "Coverage applies per state requirements",
      "Experience modification factor applied",
      "Payroll audit required annually",
      "Return-to-work programs encouraged"
    ]
  },
  "professional-liability": {
    sections: [
      {
        title: "Professional Liability/E&O",
        icon: "briefcase",
        items: [
          { name: "Per Claim Limit", limit: "$1,000,000", description: "Maximum per claim" },
          { name: "Aggregate Limit", limit: "$2,000,000", description: "Maximum per policy period" },
          { name: "Defense Costs", limit: "Inside Limits", description: "Legal defense expenses" },
          { name: "Disciplinary Proceedings", limit: "$50,000", description: "Regulatory defense coverage" },
        ]
      },
      {
        title: "Covered Acts",
        icon: "shield",
        items: [
          { name: "Negligent Acts", limit: "Full Limits", description: "Unintentional errors" },
          { name: "Errors & Omissions", limit: "Full Limits", description: "Mistakes and oversights" },
          { name: "Breach of Duty", limit: "Full Limits", description: "Failure to perform duties" },
          { name: "Misrepresentation", limit: "Full Limits", description: "Unintentional misstatements" },
          { name: "Personal Injury", limit: "Included", description: "Defamation, invasion of privacy" },
        ]
      },
      {
        title: "Extended Coverages",
        icon: "plus",
        items: [
          { name: "Prior Acts Coverage", limit: "Full Prior Acts", description: "No retroactive date limitation" },
          { name: "Worldwide Coverage", limit: "US Courts Only", description: "Coverage for work performed worldwide" },
          { name: "Subpoena Assistance", limit: "$10,000", description: "Expenses for testimony" },
          { name: "Loss of Earnings", limit: "$1,000/day", description: "Court appearance compensation" },
          { name: "Network Security", limit: "$100,000", description: "Cyber-related claims (if endorsed)" },
        ]
      }
    ],
    exclusions: [
      "Criminal or fraudulent acts",
      "Bodily injury or property damage",
      "Employment-related claims",
      "Prior & pending claims",
      "Insured vs. insured claims",
      "Contractual liability (guaranteed results)",
      "Patent and trade secret claims"
    ],
    conditions: [
      "Claims-made policy form",
      "Extended reporting period available",
      "Consent to settle provisions",
      "Deductible applies per claim"
    ]
  }
};

export const getInsuranceCoverage = (insuranceType: string): InsuranceCoverageConfig | null => {
  return INSURANCE_COVERAGE_DATA[insuranceType] || null;
};
