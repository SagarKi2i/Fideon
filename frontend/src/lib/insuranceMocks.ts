export interface InsuranceModel {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  domain: string;
  segment: "broker" | "mga" | "carrier"; // New field for insurance sub-segment
}

// Broker segment models (existing models)
export const brokerModels: InsuranceModel[] = [
  {
    id: "quote-generation",
    name: "Quote Generation Agent",
    description: "Navigate carrier websites, apply quotes, compare results, and generate proposals",
    icon: "bot",
    category: "Automation",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "policy-comparison",
    name: "Policy Comparison Engine",
    description: "Compare coverage, limits, deductibles, and exclusions across policies",
    icon: "scale",
    category: "Analysis",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "coverage-validation",
    name: "Coverage Validation & Eligibility",
    description: "Validate eligibility, business class, and binding authority",
    icon: "shield-check",
    category: "Validation",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "endorsement-intelligence",
    name: "Endorsement Intelligence",
    description: "Recommend required and optional endorsements",
    icon: "file-plus",
    category: "Advisory",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "claims-fnol",
    name: "Claims & FNOL Intelligence",
    description: "Analyze FNOL documents and detect claim red flags",
    icon: "alert-circle",
    category: "Claims",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "acord-parser",
    name: "ACORD Form Understanding",
    description: "Parse and extract data from ACORD 25, 27, 80, 85, 90, 125, 126, 140",
    icon: "file-text",
    category: "Document Processing",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "document-retrieval",
    name: "Document Retrieval",
    description: "Download policy renewals, cancellations, endorsements, memos, and invoices from carrier websites and attach to AMS",
    icon: "download",
    category: "Document Processing",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "renewal-review",
    name: "Renewal Review Assistant",
    description: "Compare expiring vs renewal policies and explain changes",
    icon: "refresh-cw",
    category: "Analysis",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "compliance-checker",
    name: "Compliance Checker",
    description: "Validate state regulations and surplus lines rules",
    icon: "clipboard-check",
    category: "Validation",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "risk-appetite",
    name: "Underwriting Risk Appetite Matching",
    description: "Match risks with carrier appetite and eligibility",
    icon: "target",
    category: "Underwriting",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "broker-advisory",
    name: "Broker Advisory Engine",
    description: "Identify underinsurance and recommend coverages",
    icon: "user-check",
    category: "Advisory",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "multi-document",
    name: "Multi-Document Analysis",
    description: "Analyze multiple documents and identify inconsistencies",
    icon: "layers",
    category: "Document Processing",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "communication-generator",
    name: "Client Communication Generator",
    description: "Generate emails, renewal letters, and proposal packets",
    icon: "mail",
    category: "Communication",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "red-flag-detector",
    name: "Red Flag Detector",
    description: "Identify missing signatures, compliance gaps, and errors",
    icon: "flag",
    category: "Validation",
    domain: "insurance",
    segment: "broker"
  },
  {
    id: "premium-estimation",
    name: "Premium Estimation Helper",
    description: "Provide premium ranges and deductible impact analysis",
    icon: "calculator",
    category: "Pricing",
    domain: "insurance",
    segment: "broker"
  }
];

// MGA segment models
export const mgaModels: InsuranceModel[] = [
  {
    id: "mga-binding-authority",
    name: "Binding Authority Manager",
    description: "Manage and track binding authority limits, usage, and compliance across programs",
    icon: "shield-check",
    category: "Authority Management",
    domain: "insurance",
    segment: "mga"
  },
  {
    id: "mga-program-underwriting",
    name: "Program Underwriting Engine",
    description: "Automated underwriting for delegated authority programs with risk scoring",
    icon: "target",
    category: "Underwriting",
    domain: "insurance",
    segment: "mga"
  },
  {
    id: "mga-bordereaux-generator",
    name: "Bordereaux Generator",
    description: "Generate premium and claims bordereaux reports for carrier partners",
    icon: "file-text",
    category: "Reporting",
    domain: "insurance",
    segment: "mga"
  },
  {
    id: "mga-capacity-matching",
    name: "Capacity Matching Engine",
    description: "Match risks to available carrier capacity and quota share arrangements",
    icon: "layers",
    category: "Placement",
    domain: "insurance",
    segment: "mga"
  },
  {
    id: "mga-producer-management",
    name: "Producer Management Hub",
    description: "Manage producer appointments, commissions, and production tracking",
    icon: "user-check",
    category: "Distribution",
    domain: "insurance",
    segment: "mga"
  },
  {
    id: "mga-treaty-compliance",
    name: "Treaty Compliance Monitor",
    description: "Monitor adherence to reinsurance treaty terms and conditions",
    icon: "clipboard-check",
    category: "Compliance",
    domain: "insurance",
    segment: "mga"
  }
];

// Carrier segment models
export const carrierModels: InsuranceModel[] = [
  {
    id: "carrier-submission-intake",
    name: "Submission Intake Engine",
    description: "Automatically process, classify, and route incoming submissions from brokers and MGAs",
    icon: "inbox",
    category: "Submission Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-submission-triage",
    name: "Submission Triage Agent",
    description: "AI-powered triage to prioritize submissions by appetite match and profitability potential",
    icon: "filter",
    category: "Submission Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-risk-scoring",
    name: "Risk Scoring Model",
    description: "Advanced risk scoring using predictive analytics and loss modeling",
    icon: "activity",
    category: "Underwriting",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-pricing-engine",
    name: "Actuarial Pricing Engine",
    description: "Calculate technical premium with expense loading and profit margins",
    icon: "calculator",
    category: "Pricing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-claims-intake",
    name: "Claims Intake Processor",
    description: "Automated claims intake with FNOL capture, validation, and assignment",
    icon: "alert-circle",
    category: "Claims Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-claims-adjudication",
    name: "Claims Adjudication Engine",
    description: "AI-assisted claims assessment, reserve setting, and settlement recommendations",
    icon: "scale",
    category: "Claims Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-fraud-detection",
    name: "Claims Fraud Detector",
    description: "Machine learning fraud detection with pattern analysis and SIU referrals",
    icon: "shield-alert",
    category: "Claims Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-subrogation",
    name: "Subrogation Recovery Agent",
    description: "Identify and pursue subrogation opportunities to recover paid claims",
    icon: "rotate-ccw",
    category: "Claims Processing",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-policy-issuance",
    name: "Policy Issuance Engine",
    description: "Automated policy document generation, delivery, and waterfall processing",
    icon: "file-check",
    category: "Policy Admin",
    domain: "insurance",
    segment: "carrier"
  },
  {
    id: "carrier-reinsurance",
    name: "Reinsurance Manager",
    description: "Manage cessions, treaty placements, and facultative arrangements",
    icon: "repeat",
    category: "Reinsurance",
    domain: "insurance",
    segment: "carrier"
  }
];

// Combined insurance models for backward compatibility
export const insuranceModels: InsuranceModel[] = [
  ...brokerModels,
  ...mgaModels,
  ...carrierModels
];

export function getMockInsuranceResponse(modelId: string, prompt: string): string {
  const responses: Record<string, string> = {
    "quote-generation": `**Quote Comparison Analysis**

Based on the quotes received from the selected carriers, here's my comprehensive analysis:

**Premium Comparison**
The premiums vary significantly across carriers, reflecting different risk assessment methodologies and discount structures. The lowest premium offers competitive pricing but should be evaluated against coverage quality.

**Coverage Assessment**
All quotes meet your requested coverage limits. However, there are subtle differences in policy exclusions and endorsements that could impact claims outcomes.

**Key Recommendations:**
1. **Best Value**: Consider the carrier offering the best balance of premium, deductible, and included features
2. **Claims Reputation**: Factor in each carrier's claims satisfaction ratings
3. **Bundling Opportunities**: Some carriers offer additional discounts for bundling multiple policies

**Risk Considerations:**
- Lower deductibles provide better out-of-pocket protection but increase premiums
- Multi-policy discounts can reduce overall insurance costs by 10-25%
- Consider each carrier's financial strength rating for long-term security

**Next Steps:**
Select your preferred quote and I'll generate a professional proposal ready to send to the insured.`,

    "policy-comparison": `**Policy Comparison Analysis**

Based on your request, here's a comprehensive comparison:

**Coverage Limits:**
• Policy A: General Liability $1M/$2M aggregate
• Policy B: General Liability $2M/$4M aggregate
✓ Policy B provides higher limits

**Deductibles:**
• Policy A: $5,000 per occurrence
• Policy B: $2,500 per occurrence
✓ Policy B has lower out-of-pocket costs

**Key Gaps Identified:**
⚠️ Policy A missing Cyber Liability coverage
⚠️ Neither policy includes Employment Practices Liability
⚠️ Policy A has water damage exclusion that Policy B covers

**Recommendations:**
1. Consider Policy B for better coverage limits
2. Add Cyber Liability endorsement ($50M-$100M coverage)
3. Review EPLI options for employment protection

**Summary:** Policy B offers superior protection with 25% higher premiums but significantly better coverage breadth and lower deductibles.`,

    "coverage-validation": `**Coverage Validation Report**

**Eligibility Status:** ✓ APPROVED

**Business Classification:**
• SIC Code: 7372 (Business Services - Software)
• NAICS: 541511 (Custom Computer Programming)
✓ Classification verified and eligible

**Required Information:**
✓ Annual revenue provided
✓ Years in business confirmed
✓ Loss history documented
⚠️ Missing: Employee count breakdown by role

**Binding Authority Check:**
✓ Within authority limits ($500K premium)
✓ No prior losses exceeding threshold
✓ Risk appetite criteria met

**Renewal Eligibility:**
✓ No outstanding premium due
✓ No material changes requiring reunderwriting
✓ Eligible for automatic renewal

**Action Required:** Please provide detailed employee breakdown before binding.`,

    "endorsement-intelligence": `**Endorsement Recommendations**

**Required Regulatory Endorsements:**
1. ✓ Waiver of Subrogation (Required for lease agreement)
2. ✓ Additional Insured - Landlord (Commercial lease requirement)
3. ⚠️ MISSING: Workers Comp Certificate of Insurance

**Recommended Optional Coverages:**
1. **Hired & Non-Owned Auto** - $15/month
   Risk: Employees using personal vehicles for business
   
2. **Cyber Liability Enhancement** - $85/month
   Risk: Customer data breach exposure
   
3. **Equipment Breakdown** - $40/month
   Risk: $200K+ in specialized equipment

**Missing Critical Endorsements:**
⚠️ Professional Liability tail coverage
⚠️ Contract-required $5M umbrella policy

**Fee Schedule Impact:**
• Current total: $4,250/year
• With recommended: $5,890/year (+38%)
• Risk reduction: Estimated $2M+ in uncovered exposure

**Priority Action:** Add Workers Comp certificate immediately to avoid contract breach.`,

    "claims-fnol": `**First Notice of Loss (FNOL) Summary**

**Claim Overview:**
• Date of Loss: January 15, 2025
• Time: 2:30 PM EST
• Location: 1234 Business Park Dr, Chicago, IL

**Cause of Loss:**
Primary: Water damage from burst pipe
Contributing: Extreme cold weather (-15°F)

**Extracted Key Information:**
✓ Affected area: 2,500 sq ft office space
✓ Damaged property: Computers, furniture, documents
✓ Estimated value: $75,000-$95,000
✓ No injuries reported

**Missing Information:**
⚠️ No photos of damage provided
⚠️ Plumber's report pending
⚠️ Tenant notification timeline unclear

**Red Flags Detected:**
🚩 Loss occurred outside business hours
🚩 Building security system was disabled
🚩 Similar claim filed 18 months ago

**Next Steps:**
1. Assign adjuster within 24 hours
2. Request photo documentation
3. Schedule site inspection
4. Obtain plumber's assessment report
5. Review security footage

**Claim Submission Summary:** Standard commercial property claim with water damage. Recommend SIU review due to prior similar claim. Priority: Medium-High.`,

    "acord-forms": `**ACORD Form Analysis**

**Form Identified:** ACORD 25 - Certificate of Liability Insurance

**Key Fields Extracted:**
✓ Producer: ABC Insurance Brokers
✓ Insured: Tech Solutions Inc.
✓ Policy #: GL-2025-789456
✓ Effective: 01/01/2025 - 01/01/2026

**Coverage Information:**
• General Liability: $1M per occurrence / $2M aggregate
• Products/Completed Ops: $2M aggregate
• Personal & Advertising Injury: $1M
• Medical Expense: $10,000 any one person
• Damage to Premises Rented: $500,000

**Additional Insureds:**
✓ Property Owner - 123 Main Street LLC
✓ Certificate Holder listed

**Missing Details:**
⚠️ Workers Compensation limits not specified
⚠️ Automobile liability section incomplete
⚠️ Umbrella/Excess liability information absent

**Risk Summary:**
Standard commercial general liability coverage with adequate limits for most operations. Missing auto and workers comp details may indicate coverage gaps. Recommend requesting complete ACORD 125 for commercial auto coverage verification.

**Compliance Status:** Certificate meets most contract requirements but needs supplemental documentation for complete coverage verification.`,

    "document-retrieval": `**Document Retrieval Results**

**Request Summary:**
${prompt}

---

## ✅ Documents Successfully Retrieved

### 📄 Policy Renewal Notice
- **Status:** Downloaded & Attached
- **File:** POL-2025-12345_Renewal_Notice.pdf
- **Size:** 245 KB
- **Effective Date:** March 1, 2025

### 📝 Endorsement - Additional Insured
- **Status:** Downloaded & Attached
- **File:** POL-2025-12345_Endorsement_AI.pdf
- **Size:** 128 KB
- **Endorsement #:** END-2025-001

### 💰 Premium Invoice
- **Status:** Downloaded & Attached
- **File:** INV-2025-67890.pdf
- **Size:** 89 KB
- **Amount Due:** $8,450.00
- **Due Date:** February 15, 2025

### 📋 Policy Memo
- **Status:** Downloaded & Attached
- **File:** MEMO-2025-Coverage_Update.pdf
- **Size:** 156 KB

---

## 📂 AMS Attachment Summary

**Target System:** Applied Epic
**Client Record:** ABC Corporation
**Policy:** Commercial Package - GL/Property

| Document | Status | AMS Location |
|----------|--------|--------------|
| Renewal Notice | ✅ Attached | Policies > Documents |
| Endorsement | ✅ Attached | Policies > Endorsements |
| Invoice | ✅ Attached | Accounting > Invoices |
| Memo | ✅ Attached | Client > Correspondence |

---

## 📊 Retrieval Statistics

- **Documents Found:** 4
- **Successfully Downloaded:** 4
- **Attached to AMS:** 4
- **Total Size:** 618 KB
- **Processing Time:** 12.3 seconds

**Next Sync:** Documents will auto-sync on policy changes.`,

    "renewal-review": `**Renewal Policy Review**

**Rate Change Analysis:**
Previous Premium: $8,450/year
Renewal Premium: $9,295/year
Increase: $845 (+10%)

**Rate Change Explanation:**
• Industry loss trends: +5%
• Territory rate adjustment: +3%
• Claims experience: +2% (one claim in period)
• Coverage enhancements: No charge

**Coverage Changes:**

INCREASED LIMITS:
✓ General Liability: $1M → $2M per occurrence
✓ Cyber Coverage: $1M → $2M
✓ Business Interruption: 60 → 90 days

REMOVED EXCLUSIONS:
✓ Communicable disease exclusion lifted
✓ Civil authority coverage restored

NEW ENDORSEMENTS ADDED:
✓ Active Assailant Coverage ($250K)
✓ Dependent Property Coverage

**Underwriting Questions:**
1. Has revenue increased more than 25%? → No change reported
2. Any new locations or operations? → None
3. Updated employee count? → 47 → 52 employees
4. Safety improvements? → New security system installed

**Broker Recommendations:**
✓ ACCEPT - Excellent renewal terms
• Rate increase below market average (10% vs 15% market)
• Significant coverage improvements at minimal cost
• Claims-free discount preserved despite one small claim
• Carrier commitment for 3-year rate guarantee available

**Action Required:** Accept renewal by December 15, 2024 to lock in rate guarantee.`,

    "compliance-checker": `**Compliance Validation Report**

**State Regulation Check:** Illinois Commercial Insurance

**Admitted Status:**
✓ COMPLIANT - Carrier is admitted in Illinois
✓ License #: 123456-IL
✓ AM Best Rating: A (Excellent)
✓ Financial strength verified

**Surplus Lines Rules:**
N/A - Standard market placement
(No surplus lines filing required)

**Cancellation Rules:**
✓ COMPLIANT with Illinois requirements:
• 30-day notice for non-payment
• 60-day notice for cancellation
• 10-day notice shown on policy
⚠️ WARNING: 10 days insufficient - requires correction

**Certificate Requirements:**
✓ ACORD 25 properly formatted
✓ Producer license verified
✓ Additional insured endorsements attached
⚠️ MISSING: Waiver of subrogation certificate

**Broker of Record (BOR):**
✓ Valid BOR on file dated 01/15/2025
✓ Properly executed by insured
✓ No competing BORs detected
⚠️ Expires in 60 days - renewal recommended

**State-Specific Requirements:**
✓ Workers Comp meets IL minimum requirements
✓ Auto liability meets IL financial responsibility law
⚠️ Missing required terrorism disclosure

**Compliance Score:** 85/100

**Critical Issues (Must Fix):**
1. Update cancellation notice period to 30/60 days
2. Add missing waiver of subrogation certificate
3. Provide terrorism coverage disclosure

**Recommendation:** Minor corrections needed before binding. All issues addressable within 48 hours.`,

    "risk-appetite": `**Underwriting Risk Appetite Analysis**

**Risk Profile Submitted:**
Industry: Technology/Software Development
Revenue: $5.2M annually
Employees: 48
Years in Business: 7
Location: Austin, TX

**Carrier Matching Results:**

**HIGH MATCH (90%+):**
1. **TechGuard Insurance** - 95% match
   ✓ Specializes in tech E&O
   ✓ Excellent cyber appetite
   ✓ Fast turnaround (48 hours)
   Estimated Premium: $8,500-$10,200

2. **Digital Assurance LLC** - 92% match
   ✓ Strong tech sector focus
   ✓ Competitive pricing
   ✓ Claims handling reputation
   Estimated Premium: $7,800-$9,500

**MODERATE MATCH (70-89%):**
3. **United Commercial** - 85% match
   ⚠️ Requires additional underwriting questions
   Premium: $9,200-$11,500

**Eligibility Scoring:**
✓ Revenue within appetite (85/100)
✓ Industry classification match (95/100)
✓ Years in business (90/100)
✓ Clean loss history (100/100)
⚠️ Location consideration (75/100) - TX hail exposure

**Missing Underwriting Information:**
1. Detailed revenue breakdown by service line
2. Client contract details (avg size, terms)
3. Cybersecurity measures documentation
4. Professional liability claims history (5+ years)
5. Business continuity plan details

**Market Submission Checklist:**
✓ ACORD application completed
✓ Loss runs (5 years) attached
✓ Financial statements current
⚠️ MISSING: Cybersecurity questionnaire
⚠️ MISSING: Sample client contracts
⚠️ MISSING: IT security policy documentation

**Recommendation:** Submit to TechGuard and Digital Assurance first tier. Complete missing documentation will improve terms and pricing by estimated 10-15%.`,

    "broker-advisory": `**Broker Advisory Report**

**Underinsurance Analysis:**

CRITICAL GAPS IDENTIFIED:
🚨 **Building Value:** $2M insured / $3.2M actual
   Risk Exposure: $1.2M underinsured (37.5%)
   Recommendation: Increase to $3.5M (includes appreciation)

🚨 **Business Income:** 60-day coverage / 120-day needed
   Risk: Insufficient for complete rebuild timeline
   Recommendation: Extend to 180 days with extended period

**Recommended Coverage Additions:**

1. **Cyber Liability - CRITICAL**
   Current: None
   Recommended: $5M coverage
   Cost: ~$3,500/year
   Why: Customer PII exposure, 48% of tech firms hit in 2024

2. **Employment Practices Liability**
   Current: None
   Recommended: $2M coverage
   Cost: ~$1,800/year
   Why: 52 employees = elevated risk, avg claim $75K

3. **Crime/Employee Dishonesty**
   Current: $50K
   Recommended: $500K
   Cost: +$650/year
   Why: Inadequate for accounts receivable and funds transfer risks

**Exposed Risks:**

⚠️ **Technology E&O:** Coverage exists but $1M limit low for revenue size
⚠️ **Contractual Liability:** Not all contracts covered by current limits
⚠️ **Supply Chain:** No contingent business interruption coverage
⚠️ **Key Person:** No coverage for critical employee loss

**Client Advisory Summary:**

**Immediate Actions (Next 30 Days):**
1. Increase building coverage to $3.5M
2. Add $5M cyber liability policy
3. Extend business income to 180 days

**Priority Additions (Next 60 Days):**
4. EPLI coverage $2M
5. Crime coverage increase to $500K
6. Review all vendor contracts for insurance requirements

**Long-term Recommendations (Next Renewal):**
7. Umbrella policy consideration ($5M+)
8. Key person insurance evaluation
9. Supply chain disruption coverage

**Total Current Premium:** $12,450/year
**Recommended Premium:** $18,900/year
**Increased Protection:** $12M+ in additional coverage
**Risk Reduction:** 85% of major exposure gaps closed

**Overall Risk Grade:**
Current: C+ (Multiple critical gaps)
With Changes: A- (Comprehensive protection)

Would you like me to prepare proposals for any of these recommendations?`,

    "multi-document": `**Multi-Document Analysis Report**

**Documents Analyzed:**
1. Current Policy - GL-2025-789
2. Renewal Quote - GL-2026-456
3. Certificate of Insurance - COI-2025-123
4. Loss Run Report - 5 Year
5. Endorsement Schedule

**Inconsistencies Detected:**

🚨 **CRITICAL:**
• Policy shows $2M liability / COI shows $1M
• Renewal removes flood coverage vs current policy includes
• Loss run shows 2 claims / Application states claims-free

⚠️ **SIGNIFICANT:**
• Effective dates mismatched (2 day gap in coverage)
• Additional insured on COI not listed in policy
• Premium amounts differ ($200/month variance)

**Submission Package Summary:**

**Risk Profile:**
• Insured: Tech Solutions Inc.
• Location: Multiple - HQ Austin, TX + 2 satellite offices
• Operations: Software development and consulting
• Annual Revenue: $5.2M
• Employees: 48 full-time
• Years in Business: 7

**Current Coverage Summary:**
• General Liability: $1M/$2M (conflicting docs)
• Professional Liability: $2M/$4M
• Cyber: $1M
• Property: $800K building / $400K contents
• Business Income: 90 days
• Workers Comp: Statutory limits

**Key Risk Data Extracted:**
✓ Loss frequency: 2 claims in 5 years
✓ Total incurred: $45,000
✓ Claims closed: Both settled
✓ Safety programs: Yes - documented
✓ Quality certifications: ISO 9001

**Document Quality Issues:**
⚠️ Missing signatures on 2 endorsements
⚠️ COI expired 30 days ago
⚠️ Outdated revenue figures in application

**Consolidated Recommendation:**
Before proceeding with renewal:
1. Clarify actual liability limits (obtain declarations page)
2. Confirm flood coverage inclusion/exclusion
3. Update loss history on application
4. Close coverage gap
5. Obtain fresh COI with correct limits
6. Collect missing signatures

**Estimated Resolution Time:** 3-5 business days for complete clean submission package.`,

    "client-communication": `**Generated Client Communication**

---

**SUBJECT:** Your 2026 Insurance Renewal - Action Required by Dec 15

Dear [Client Name],

I hope this message finds you well. I wanted to reach out regarding your upcoming insurance renewal, which takes effect on January 1, 2026.

**Renewal Summary:**

I'm pleased to share that we've secured competitive renewal terms for your coverage:

• **Premium:** $9,295/year (10% increase from $8,450)
• **Enhanced Coverage:** Liability limits increased from $1M to $2M at no extra charge
• **New Protections:** Added Active Assailant and Cyber coverage enhancements

**Why the Rate Increase?**

While a 10% increase may seem significant, it's actually below the market average of 15% for similar businesses. The increase reflects:
- Industry-wide loss trends affecting all insurers
- One claim from last year (water damage incident)
- Expanded coverage and higher limits included

**What Makes This a Good Renewal:**

✓ Coverage improvements worth $2,000+ provided at minimal cost
✓ Rate guarantee locked for 3 years if accepted by December 15
✓ No coverage gaps or compliance issues
✓ Same carrier continuity (no need to remarket)

**Action Required:**

Please review the attached renewal quote and let me know by **December 15, 2024** if you'd like to proceed. This deadline is important to secure the rate guarantee.

If you have any questions or would like to discuss coverage options, I'm happy to schedule a call at your convenience.

**Recommended Next Steps:**
1. Review attached renewal documents
2. Confirm any business changes since last year
3. Approve renewal by December 15 to lock rates

Thank you for your continued trust in our agency. I look forward to serving your insurance needs in 2026.

Best regards,

[Your Name]
[Agency Name]
[Contact Information]

---

**Attachments:**
- Renewal Quote Summary
- Policy Comparison Sheet
- Updated Certificate of Insurance

---

*This communication template can be customized for your specific client relationship and communication style.*`,

    "red-flag": `**Red Flag Detection Report**

**Document Review Completed:** 5 documents analyzed

**CRITICAL ISSUES (Immediate Action Required):**

🚨 **Missing Signatures:**
• Waiver of Subrogation endorsement - unsigned
• Additional Insured endorsement CG 20 10 - no signature
• Application page 3 - authorization signature absent
**Impact:** Endorsements may be void, coverage gaps exist

🚨 **Duplicate Endorsements:**
• CG 20 10 04 13 appears twice with different additional insureds
• Additional Insured - Managers endorsement duplicated
**Impact:** Premium charged twice, potential coverage conflicts

🚨 **Incorrect Limits:**
• Certificate shows $2M General Liability
• Policy declarations show $1M General Liability
• Contract requires $2M minimum
**Impact:** Contract non-compliance, potential breach

**SIGNIFICANT ISSUES (Review Required):**

⚠️ **AM Best Rating Concerns:**
• Listed carrier AM Best rating: B++ (Good)
• Contract requires A- (Excellent) or better
**Impact:** Does not meet contractual requirements

⚠️ **Compliance Gaps:**
• Workers Comp certificate expired 45 days ago
• No terrorism disclosure provided (required in IL)
• Cancellation notice period shows 10 days (requires 30)

⚠️ **Coverage Inconsistencies:**
• Cyber policy effective date: 1/1/2025
• All other policies effective: 1/15/2025
• 14-day gap in cyber coverage

**MINOR ISSUES (Administrative):**

• Producer license number incorrect format
• NAIC code transposed (correct carrier, wrong code)
• Policy number format doesn't match carrier standard

**Financial Red Flags:**

✓ Premium payment current (no issues)
✓ No returned payment history
⚠️ Installment plan shows 15% finance charge (high)

**Priority Action Items:**

**IMMEDIATE (Within 24 Hours):**
1. Obtain missing signatures on endorsements
2. Correct liability limits on certificate
3. Remove duplicate endorsements and adjust premium

**URGENT (Within 1 Week):**
4. Address AM Best rating requirement with client
5. Update Workers Comp certificate
6. Close 14-day cyber coverage gap

**ROUTINE (Within 2 Weeks):**
7. Correct administrative errors (license, NAIC)
8. Provide terrorism disclosure
9. Update cancellation notice provisions

**Risk Assessment:**
Current Status: HIGH RISK - Multiple compliance and coverage issues
Estimated Resolution Time: 5-7 business days
Recommendation: Do not bind until critical issues resolved

**Summary:** Found 11 red flags across 5 documents. Three critical issues require immediate attention to avoid coverage gaps and contract violations. Recommend complete document review and corrections before proceeding with policy binding.`,

    "premium-estimation": `**Premium Estimation Analysis**

**Disclaimer:** *This is an estimated range only, not an actual quote. Actual premium determined by underwriting.*

---

**Risk Profile:**
• Industry: Technology/Software
• Revenue: $5.2M
• Employees: 48
• Location: Austin, TX
• Years in Business: 7
• Loss History: 2 claims / 5 years

**Estimated Premium Ranges:**

**General Liability:**
Low: $3,200/year
High: $4,800/year
Median Market: $3,900/year

**Professional Liability (E&O):**
Low: $4,500/year
High: $7,200/year
Median Market: $5,800/year

**Cyber Liability:**
Low: $2,800/year
High: $4,500/year
Median Market: $3,600/year

**Property Coverage:**
Low: $2,100/year
High: $3,200/year
Median Market: $2,600/year

**Workers Compensation:**
Low: $18,000/year
High: $24,000/year
Median Market: $21,000/year

**TOTAL ESTIMATED PREMIUM:**
**Low Range:** $30,600/year
**High Range:** $43,700/year
**Most Likely:** $36,900/year

---

**Deductible Impact Analysis:**

**Current Deductible: $2,500**

| Deductible | Estimated Annual Premium | Annual Savings |
|------------|-------------------------|----------------|
| $1,000     | $38,400                 | Baseline       |
| $2,500     | $36,900 (current)       | -$1,500        |
| $5,000     | $34,800                 | -$3,600        |
| $10,000    | $32,100                 | -$6,300        |

**Recommendation:** $5,000 deductible offers optimal balance
- Saves $3,600/year vs $1,000 deductible
- Break-even on one claim scenario: 1.4 years
- Based on your 2.5 year average between claims

---

**Coverage Limit Impact:**

**General Liability Limit Options:**

| Limit | Premium Impact | Risk Protection |
|-------|---------------|-----------------|
| $1M/$2M | Baseline ($3,900) | Minimum adequate |
| $2M/$4M | +$1,200/year | **Recommended** |
| $3M/$6M | +$2,400/year | Enhanced protection |
| $5M/$10M | +$4,800/year | Maximum protection |

**Analysis:** $2M/$4M recommended
- Meets most contract requirements
- Only 30% premium increase
- Doubles protection for claims severity
- Industry standard for $5M+ revenue companies

---

**Multi-Year Discount Opportunity:**

• 2-Year Policy: -5% ($1,845 savings)
• 3-Year Policy: -8% ($2,952 savings)
• Rate guarantee included

---

**Bundle Savings:**

Placing all coverage with one carrier:
- Expected discount: 10-15%
- Estimated savings: $3,690-$5,535/year
- Simplified administration
- Single renewal date

---

**Final Recommendations:**

**Optimal Package:**
• $2M/$4M General Liability
• $5,000 deductible
• 3-year policy term
• Bundle with single carrier

**Estimated Total:** $31,200-$33,500/year
**Savings vs Standard:** $5,400-$10,200/year

Would you like me to proceed with formal quotes from carriers based on this analysis?`,

    // MGA Models
    "mga-binding-authority": `**Binding Authority Dashboard**

**Authority Overview:**
• Program: Commercial Property - Small Business
• Carrier: National Indemnity Insurance
• Authority Effective: 01/01/2024 - 12/31/2024
• Territory: TX, OK, NM, AZ

**Usage Summary:**

| Metric | Current | Limit | % Used |
|--------|---------|-------|--------|
| Written Premium | $4.2M | $10M | 42% |
| Maximum Single Risk | $450K | $500K | 90% |
| Policies Bound | 847 | 1,500 | 56% |
| Average Premium | $4,958 | - | - |

**Authority Utilization by Month:**
📊 Jan: 8% | Feb: 12% | Mar: 15% | Apr: 18% | May: 22% | Jun: 28% | Jul: 35% | Aug: 38% | Sep: 42%

**Compliance Status:** ✅ COMPLIANT
• All bordereaux submitted on time
• Claims reporting current
• Premium remittance up to date
• Quarterly audit passed

**Binding Authority Exceptions (YTD):**
• Referrals to carrier: 23
• Approved: 21 (91%)
• Declined: 2 (9%)
• Average response time: 1.2 days

**Upcoming Deadlines:**
⚠️ Q4 Bordereaux due: Oct 15
⚠️ Authority renewal meeting: Nov 1
⚠️ Annual audit: Dec 15`,

    "mga-program-underwriting": `**Program Underwriting Decision**

**Submission:** SUB-2025-78456
**Program:** Artisan Contractors
**Risk Score:** 78/100 (ACCEPTABLE)

**Automated Underwriting Decision:** ✅ APPROVED

**Risk Assessment:**

| Factor | Score | Weight | Contribution |
|--------|-------|--------|--------------|
| Years in Business | 85 | 20% | 17 |
| Loss History | 72 | 25% | 18 |
| Territory | 80 | 15% | 12 |
| Operations | 75 | 20% | 15 |
| Financial Stability | 82 | 20% | 16 |
| **Total** | | | **78** |

**Eligibility Checklist:**
✅ Revenue within program guidelines ($500K-$5M)
✅ Years in business ≥ 3 years
✅ Loss ratio < 60%
✅ No contractors exclusions violations
✅ Proper licensing verified
✅ Territory within authority

**Program Rating:**
• Base Premium: $8,450
• Experience Credit: -8% (-$676)
• Safety Program Credit: -5% (-$389)
• Territory Factor: +3% (+$221)
• **Final Premium: $7,606**

**Coverage Provided:**
• General Liability: $1M/$2M
• Products/Completed Operations: $2M
• Hired/Non-Owned Auto: $1M
• Tools & Equipment: $50K

**Binding Instructions:**
• Bind within authority
• No referral required
• Issue policy via automated workflow
• Premium due: Net 30`,

    "mga-bordereaux-generator": `**Bordereaux Report Generated**

**Report Type:** Premium Bordereaux
**Period:** September 2025
**Program:** Commercial Property Portfolio
**Carrier:** Atlantic Specialty Insurance

---

**Summary Statistics:**

| Metric | Count/Amount |
|--------|--------------|
| New Business | 45 policies / $425,000 |
| Renewals | 78 policies / $680,000 |
| Endorsements | 23 / $35,000 |
| Cancellations | 8 / -$42,000 |
| **Net Written Premium** | **$1,098,000** |

**Premium Breakdown by Class:**

| Classification | Policies | Premium | % of Total |
|---------------|----------|---------|------------|
| Office Buildings | 42 | $385,000 | 35% |
| Retail | 35 | $295,000 | 27% |
| Light Industrial | 28 | $248,000 | 23% |
| Mixed Use | 18 | $170,000 | 15% |

**Geographic Distribution:**
• Texas: 68% ($746,640)
• Oklahoma: 18% ($197,640)
• New Mexico: 9% ($98,820)
• Arizona: 5% ($54,900)

**Claim Activity:**
• New Claims: 3
• Closed Claims: 5
• Open Reserve: $125,000
• Paid YTD: $45,000

**Report Status:** ✅ Complete
**Validation:** All fields verified
**Submission:** Uploaded to carrier portal
**Confirmation:** BDX-2025-09-4578`,

    "mga-capacity-matching": `**Capacity Matching Results**

**Submission:** Large Property Account
**TIV:** $45,000,000
**Coverage:** Property, BI, Equipment

**Carrier Capacity Analysis:**

| Carrier | Available Capacity | Pricing Indication | Match Score |
|---------|-------------------|-------------------|-------------|
| Carrier A | $15M (33%) | $0.42/$100 | 92% ✅ |
| Carrier B | $12M (27%) | $0.45/$100 | 88% |
| Carrier C | $10M (22%) | $0.48/$100 | 85% |
| Carrier D | $8M (18%) | $0.52/$100 | 78% |
| **Total** | **$45M (100%)** | **Blended: $0.46** | - |

**Recommended Placement:**

**Lead: Carrier A (33%)**
• Strong property appetite
• Fast quote turnaround
• Claims team rated 4.5/5

**Following:**
• Carrier B: 27%
• Carrier C: 22%
• Carrier D: 18%

**Quota Share Terms:**
• Pro-rata premium distribution
• Single policy form
• Lead carrier claims authority
• Quarterly settlements

**Estimated Total Premium:** $207,000
**Commission:** $35,190 (17%)
**Net to Carriers:** $171,810`,

    "mga-producer-management": `**Producer Performance Dashboard**

**Producer:** Johnson Insurance Agency
**Code:** PRD-78456
**Status:** ACTIVE ✅

**Production Summary (YTD):**

| Metric | Amount | vs LY | Rank |
|--------|--------|-------|------|
| Written Premium | $1,250,000 | +15% | #12/156 |
| Policies | 245 | +8% | #18/156 |
| Avg Premium | $5,102 | +6% | #8/156 |
| Retention | 88% | +2% | #5/156 |

**Loss Ratio:** 42% ✅ (Target: <55%)

**Commission Schedule:**
• New Business: 15%
• Renewal: 12%
• Override: 2% (volume bonus)
• Current Earnings: $168,750

**Appointments:**
✅ Property (A+ carrier)
✅ General Liability (A carrier)
✅ Workers Comp (A+ carrier)
⏳ Professional Liability (pending)

**Compliance:**
✅ E&O current ($2M)
✅ License renewed
✅ Background check passed
⚠️ Annual training due: Nov 30`,

    "mga-treaty-compliance": `**Treaty Compliance Monitor**

**Treaty:** 2025 Property Excess of Loss
**Reinsurer:** Swiss Re America
**Layer:** $5M xs $1M

**Compliance Status:** ✅ COMPLIANT

**Key Treaty Terms:**

| Provision | Requirement | Status |
|-----------|-------------|--------|
| Premium Cession | Quarterly | ✅ Current |
| Claims Notice | 30 days | ✅ Compliant |
| Bordereaux | Monthly | ✅ Submitted |
| Audit Rights | Annual | Scheduled Q4 |

**Financial Summary:**

| Metric | Amount |
|--------|--------|
| Ceded Premium (YTD) | $2,450,000 |
| Recoveries (YTD) | $380,000 |
| Loss Ratio | 15.5% |
| Commission | $490,000 (20%) |

**Active Claims:**
• Open claims on treaty: 3
• Total IBNR reserve: $500,000
• Largest single loss: $850,000

**Treaty Capacity:**
• Annual limit: $25,000,000
• Used: $380,000 (1.5%)
• Remaining: $24,620,000

**Upcoming Actions:**
⚠️ Q4 premium settlement: Oct 31
⚠️ Treaty renewal negotiation: Nov 15`,

    // Carrier Models
    "carrier-submission-intake": `**Submission Intake Complete**

**Submission ID:** SUB-2025-89012
**Received:** ${new Date().toLocaleDateString()}
**Source:** Broker Portal
**Broker:** ABC Insurance Brokers

**Classification Results:**

| Document | Type | Pages | Status |
|----------|------|-------|--------|
| ACORD 125 | Application | 8 | ✅ Parsed |
| ACORD 126 | GL Supplement | 4 | ✅ Parsed |
| Loss Runs | Claims History | 3 | ✅ Extracted |
| Financials | Annual Report | 12 | ✅ Analyzed |
| SOV | Property Schedule | 6 | ✅ Validated |

**Extracted Data:**

**Insured Information:**
• Name: Tech Solutions Corp
• Address: 123 Innovation Dr, Austin, TX
• NAICS: 541512 (Computer Systems Design)
• SIC: 7371 (Computer Programming)

**Coverage Requested:**
• Commercial Package
• Effective: 03/01/2025
• Limits: $2M GL / $1M Property
• Deductible: $5,000

**Risk Metrics:**
• Revenue: $8.2M
• Employees: 62
• Years: 9
• Locations: 2

**Routing Decision:**
→ Assigned to: **Technology Unit**
→ Underwriter: Sarah Chen
→ Priority: HIGH (large account)
→ SLA: Quote within 3 days

**Quality Score:** 94/100
• Complete application ✅
• Current loss runs ✅
• Financial statements ✅
⚠️ Missing: Equipment schedule`,

    "carrier-submission-triage": `**Submission Triage Analysis**

**Queue Status:** 47 pending submissions

**AI Prioritization Results:**

| Rank | Submission | Appetite | Premium Est. | Priority |
|------|------------|----------|--------------|----------|
| 1 | SUB-89012 | 95% | $125,000 | 🔴 HIGH |
| 2 | SUB-89008 | 88% | $85,000 | 🔴 HIGH |
| 3 | SUB-89015 | 82% | $62,000 | 🟡 MEDIUM |
| 4 | SUB-89011 | 78% | $45,000 | 🟡 MEDIUM |
| 5 | SUB-89009 | 65% | $38,000 | 🟢 NORMAL |

**SUB-89012 Deep Analysis:**

**Appetite Factors:**
✅ Technology sector (target class)
✅ Revenue $5M-$15M (sweet spot)
✅ Clean loss history
✅ Multi-year opportunity
⚠️ TX coastal exposure

**Profitability Prediction:**
• Expected Loss Ratio: 42%
• Target Loss Ratio: 55%
• Profit Margin: +13% above target
• Confidence: 87%

**Competitive Intelligence:**
• Current carrier: Hartford
• Expiring premium: $115,000
• Market position: Quote at $118,000 (win probability 72%)

**Recommendation:** PURSUE AGGRESSIVELY
• High-quality risk
• Strong profit potential
• Competitive pricing possible
• Strategic account for growth`,

    "carrier-risk-scoring": `**Risk Scoring Model Output**

**Risk ID:** RSK-2025-45678
**Model Version:** v3.2.1
**Confidence:** 91%

**Overall Risk Score:** 72/100 (ACCEPTABLE)

**Component Scores:**

| Category | Score | Weight | Contribution |
|----------|-------|--------|--------------|
| Industry Risk | 78 | 25% | 19.5 |
| Geographic | 65 | 15% | 9.8 |
| Financial | 82 | 20% | 16.4 |
| Claims History | 85 | 20% | 17.0 |
| Operations | 68 | 20% | 13.6 |
| **Weighted Total** | | | **76.3** |
| Model Adjustment | | | -4.3 |
| **Final Score** | | | **72.0** |

**Risk Factors:**

**Positive:**
✅ Strong financial ratios (D/E: 0.3)
✅ 9 years in business
✅ ISO 27001 certified
✅ Dedicated safety officer

**Negative:**
⚠️ Coastal TX location (CAT exposure)
⚠️ 15% YoY growth (capacity strain)
⚠️ Recent expansion into new service line

**Predictive Analytics:**

| Metric | Prediction | Confidence |
|--------|------------|------------|
| Claim Frequency | 0.8/year | 85% |
| Average Severity | $28,000 | 78% |
| Expected Loss | $22,400 | 82% |
| Max Probable Loss | $180,000 | 72% |

**Underwriting Recommendation:**
✅ WRITE at standard terms
• Apply 5% CAT load for coastal
• Require annual loss control visit
• Quarterly financial monitoring`,

    "carrier-pricing-engine": `**Actuarial Pricing Analysis**

**Risk:** Tech Solutions Corp
**LOB:** Commercial Package
**Effective:** 03/01/2025

---

**Technical Premium Calculation:**

**General Liability:**
| Component | Calculation | Amount |
|-----------|-------------|--------|
| Base Rate | $8.2M rev × $0.85/$1000 | $6,970 |
| Class Mod | Technology services × 1.15 | $8,016 |
| Experience Mod | 0.92 (favorable losses) | $7,375 |
| Territory Factor | TX × 1.08 | $7,965 |
| Limit Factor | $2M/$4M × 1.45 | $11,549 |
| **Technical Premium** | | **$11,549** |

**Property:**
| Component | Amount |
|-----------|--------|
| Building TIV: $2.5M × $0.42 | $10,500 |
| Contents TIV: $800K × $0.55 | $4,400 |
| BI: 90 days × $1.20 | $2,160 |
| **Technical Premium** | **$17,060** |

**Package Adjustments:**
• Package Credit: -8%
• Multi-Year: -5%
• Loss Free Credit: -3%

**Expense Loading:**
| Expense | Rate | Amount |
|---------|------|--------|
| Commission | 15% | $3,948 |
| Acquisition | 5% | $1,316 |
| General Admin | 8% | $2,106 |
| Taxes/Fees | 3% | $790 |

**Profit & Contingency:** 5% = $1,316

**Final Premium:**
• Technical: $26,324
• Loaded: $35,800
• **Final Quote: $35,800**

**Indicated Price Range:**
• Floor (60% LR): $32,500
• Target (55% LR): $35,800
• Ceiling (50% LR): $39,200`,

    "carrier-claims-intake": `**Claims Intake Processing**

**Claim Number:** CLM-2025-156789
**Policy:** POL-2024-789456
**Received:** ${new Date().toLocaleDateString()} 09:23 AM
**Source:** Online Portal

---

**FNOL Capture:**

**Claimant Information:**
• Insured: ABC Manufacturing Inc
• Contact: John Smith, Risk Manager
• Phone: (512) 555-0123
• Email: jsmith@abcmfg.com

**Loss Details:**
• Date of Loss: ${new Date(Date.now() - 86400000).toLocaleDateString()}
• Time: 2:30 PM CST
• Location: 456 Industrial Blvd, Houston, TX
• Cause: Water damage - burst pipe

**Description:**
Frozen pipe burst in Warehouse B during cold snap. Water damage to inventory, equipment, and building structure. Area approximately 2,500 sq ft affected.

**Extracted Data:**
✅ Policy verified active
✅ Coverage confirmed
✅ Deductible: $5,000
✅ Property limit: $1,000,000

**Validation Results:**
✅ Timely reported (within 24 hours)
✅ Within policy period
✅ Covered peril (water damage)
⚠️ Prior claim on file (18 months ago)

**Initial Reserve:**
• Building: $25,000
• Contents: $35,000
• Equipment: $15,000
• **Total: $75,000**

**Assignment:**
→ Adjuster: Maria Garcia (ID: ADJ-4521)
→ Team: Property - Commercial
→ Priority: STANDARD
→ Contact SLA: 24 hours`,

    "carrier-claims-adjudication": `**Claims Adjudication Analysis**

**Claim:** CLM-2025-156789
**Status:** UNDER REVIEW
**Days Open:** 15

---

**Coverage Determination:**

| Coverage | Applicable | Limit | Deductible | Available |
|----------|------------|-------|------------|-----------|
| Building | ✅ YES | $1,000,000 | $5,000 | $995,000 |
| BPP | ✅ YES | $500,000 | $2,500 | $497,500 |
| BI | ✅ YES | 60 days | 48 hrs | - |
| Flood | ❌ NO | Excluded | - | - |

**Damage Assessment:**

| Category | Claimed | Verified | Recommended |
|----------|---------|----------|-------------|
| Building Repairs | $28,000 | $26,500 | $26,500 |
| Equipment | $42,000 | $38,000 | $38,000 |
| Inventory | $35,000 | $31,500 | $31,500 |
| Mitigation | $8,500 | $8,500 | $8,500 |
| **Subtotal** | $113,500 | $104,500 | $104,500 |
| Less Deductible | | | -$5,000 |
| **Net Payment** | | | **$99,500** |

**Depreciation Analysis:**
• Equipment age: 4 years
• Useful life: 10 years
• ACV adjustment: -$12,000
• Replacement cost holdback: $12,000

**AI Recommendation:** ✅ APPROVE

**Confidence Score:** 89%

**Supporting Factors:**
✅ Covered peril confirmed
✅ Damages documented
✅ Estimates reasonable
✅ No fraud indicators
✅ Subrogation potential identified

**Settlement Recommendation:**
• Issue ACV payment: $87,500
• Holdback for RCV: $12,000
• Total when repairs complete: $99,500`,

    "carrier-fraud-detection": `**Fraud Detection Analysis**

**Claim:** CLM-2025-156789
**Overall Fraud Score:** 18/100 (LOW RISK)

---

**Red Flag Indicators:**

| Indicator | Status | Score Impact |
|-----------|--------|--------------|
| Timing Anomalies | ⚪ None | 0 |
| Financial Stress | ⚪ None | 0 |
| Claim History | 🟡 Prior claim | +8 |
| Documentation Issues | ⚪ None | 0 |
| Witness/Reporting | 🟡 Weekend loss | +5 |
| Network Analysis | ⚪ Clean | 0 |
| Behavioral Signals | ⚪ None | +5 |
| **Total** | | **18** |

**Detailed Analysis:**

**Prior Claims History:**
• 1 claim in past 3 years (water damage)
• Claim paid: $45,000
• Similar cause of loss: ⚠️ Flag
• Different location: ✅ Mitigating

**Timing Analysis:**
• Loss occurred Saturday afternoon
• Reported Sunday morning (12 hours)
• Within normal reporting window

**Financial Analysis:**
✅ Company financially stable
✅ No recent layoffs
✅ Revenue consistent
✅ No pending litigation

**Network Analysis:**
✅ No suspicious vendor connections
✅ Contractor is established business
✅ No prior insured relationships flagged

**Recommendation:** 
✅ PROCEED - No SIU referral needed

**Monitoring Notes:**
• Standard documentation review
• Verify contractor independence
• Compare repair costs to market rates`,

    "carrier-subrogation": `**Subrogation Recovery Analysis**

**Claim:** CLM-2025-156789
**Recovery Potential:** HIGH (82%)

---

**Third Party Liability Assessment:**

**Potential Targets:**

| Party | Liability | Est. Recovery | Confidence |
|-------|-----------|---------------|------------|
| Plumber (Maintenance) | Negligence | $65,000 | 85% |
| Building Owner | Shared | $15,000 | 60% |
| HVAC Contractor | Contributing | $10,000 | 45% |
| **Total Potential** | | **$90,000** | - |

**Primary Target: Johnson Plumbing LLC**

**Liability Basis:**
• Contracted for pipe maintenance
• Last inspection: 45 days prior
• Failed to winterize pipes
• Clear negligence standard

**Evidence Collected:**
✅ Maintenance contract on file
✅ Inspection records obtained
✅ Expert report supports negligence
✅ Photos of failed insulation
✅ Weather data (freeze warning issued)

**Recovery Timeline:**
1. Demand letter: Week 1
2. Negotiation period: Weeks 2-4
3. Settlement target: Week 6
4. Litigation if needed: Month 3+

**Financial Analysis:**

| Metric | Amount |
|--------|--------|
| Claim Paid | $99,500 |
| Expected Recovery | $75,000 |
| Recovery Rate | 75% |
| Legal Costs | $8,000 |
| Net Recovery | $67,000 |
| ROI | 838% |

**Recommendation:**
✅ PURSUE SUBROGATION
• High probability of recovery
• Strong evidence package
• Solvent third party
• Cost-effective litigation risk`,

    "carrier-policy-issuance": `**Policy Issuance Status**

**Policy Number:** POL-2025-567890
**Insured:** Tech Solutions Corp
**Status:** ✅ ISSUED

---

**Issuance Timeline:**

| Step | Status | Timestamp |
|------|--------|-----------|
| Quote Accepted | ✅ Complete | Feb 15, 10:23 AM |
| Payment Received | ✅ Complete | Feb 15, 10:25 AM |
| Underwriting Final | ✅ Complete | Feb 15, 10:30 AM |
| Document Generation | ✅ Complete | Feb 15, 10:31 AM |
| Quality Check | ✅ Complete | Feb 15, 10:32 AM |
| Delivery | ✅ Complete | Feb 15, 10:33 AM |

**Total Processing Time:** 10 minutes

**Documents Generated:**

| Document | Pages | Status |
|----------|-------|--------|
| Declarations Page | 2 | ✅ Issued |
| Policy Form (CP 00 10) | 45 | ✅ Issued |
| Endorsement Schedule | 8 | ✅ Issued |
| Certificate of Insurance | 1 | ✅ Issued |
| Premium Invoice | 2 | ✅ Issued |

**Delivery Confirmation:**
• Email: jsmith@techsolutions.com ✅ Delivered
• Broker Portal: ABC Brokers ✅ Posted
• Archive: Document Management ✅ Stored

**Policy Details:**
• Effective: 03/01/2025
• Expiration: 03/01/2026
• Premium: $35,800
• Payment: Paid in Full

**Waterfall Processing:**
✅ Commission calculated: $5,370
✅ Taxes filed: TX $1,074
✅ Reinsurance cession: $3,580
✅ Accounting posted`,

    "carrier-reinsurance": `**Reinsurance Management Dashboard**

**Program:** 2025 Property Treaty

---

**Treaty Structure:**

| Layer | Attachment | Limit | Premium | Reinsurer |
|-------|------------|-------|---------|-----------|
| QS | $0 | 20% | $12.4M | Munich Re |
| 1st XS | $1M | $4M | $2.8M | Swiss Re |
| 2nd XS | $5M | $10M | $1.5M | Lloyd's |
| CAT XS | $15M | $85M | $8.2M | Panel |

**YTD Cession Activity:**

| Metric | Amount |
|--------|--------|
| Gross Written Premium | $62,000,000 |
| Ceded Premium | $24,900,000 |
| Retained Premium | $37,100,000 |
| Cession Ratio | 40.2% |

**Claims Activity:**

| Type | Gross | Ceded | Net |
|------|-------|-------|-----|
| Paid Losses | $18.5M | $7.2M | $11.3M |
| Outstanding | $12.3M | $4.8M | $7.5M |
| IBNR | $8.0M | $3.1M | $4.9M |
| **Total Incurred** | **$38.8M** | **$15.1M** | **$23.7M** |

**Treaty Performance:**
• Gross Loss Ratio: 62.6%
• Net Loss Ratio: 63.9%
• Ceding Commission: 22%
• Profit Commission: Projected 8%

**Facultative Placements (YTD):**
• Submissions: 45
• Placed: 38 (84%)
• Declined: 7
• Total Fac Premium: $3.2M

**Upcoming Renewals:**
⚠️ CAT Treaty: Dec 31, 2025
⚠️ Casualty QS: Jan 1, 2026`
  };

  const model = insuranceModels.find(m => m.id === modelId);
  
  return responses[modelId] || `**${model?.name || "Insurance Analysis"}**

Thank you for your request: "${prompt}"

${model ? `This capability provides ${model.description.toLowerCase()}.` : ''}

**Mock Response:** This is a demonstration of the ${model?.name || "insurance capability"}. In production, this would analyze your specific documents and data to provide detailed, actionable insurance intelligence.

Contact your administrator to enable full AI processing for production use.`;
}
