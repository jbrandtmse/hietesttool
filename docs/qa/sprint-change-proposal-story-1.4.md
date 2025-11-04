# Sprint Change Proposal: IHE Transaction Scope Clarification

**Date:** 2025-11-04  
**Prepared By:** Bob (Scrum Master)  
**Interaction Mode:** YOLO (Batched Analysis)  
**Status:** Pending User Approval

---

## Executive Summary

During QA review of Story 1.4 (Project Structure & Dependencies), a transaction specification clarification was identified in the README.md. The project currently references **ITI-8** (PIX Add v2 - pipe-delimited HL7 v2 format), but the actual implementation and all project documentation correctly uses **ITI-44** (PIX Add v3 - HL7v3 XML format). This proposal corrects the documentation inconsistency and clarifies Phase 1 vs Phase 2 transaction scope.

**Impact Level:** LOW - Documentation correction only, no code or architecture changes required.

---

## Section 1: Change Context & Issue Definition

### Triggering Story
**Story 1.4:** Project Structure & Dependencies (currently in QA review)

### Issue Type
✅ **Requirement Clarification** - Documentation inaccuracy discovered during QA review

### Core Problem Statement
README.md incorrectly lists **ITI-8 (Patient Identity Feed - PIX Add v2)** in the acknowledgments section, when the project actually implements **ITI-44 (Patient Identity Feed HL7v3 - PIX Add v3)**. Additionally, Phase 1 vs Phase 2 transaction scope needs clarification.

### Evidence & Supporting Information

**From User Clarification:**
- Phase 1 should include: **ITI-44** (PIX v3 Identity Feed) and **ITI-41** (Provide and Register Document Set-b)
- Phase 2 should include: **ITI-45** (PIX Query v3), **ITI-18** (Registry Stored Query), **ITI-43** (Retrieve Document Set)
- ITI-8 (PIX v2) is NOT required for this project and should be excluded

**From Code Analysis:**
- All spike findings (Stories 1.1, 1.3) reference ITI-44, not ITI-8
- `src/ihe_test_util/ihe_transactions/pix_add.py` implements ITI-44 (HL7v3 XML)
- Architecture Decision Record ADR-003 references ITI-44
- Epic 5 is correctly titled "PIX Add Transaction Implementation" and implements ITI-44

**Conclusion:** The implementation is CORRECT. Only README.md contains incorrect transaction reference.

---

## Section 2: Epic Impact Assessment

### Current Epic (Epic 1)
✅ **Epic 1 is structurally sound** - only requires documentation correction in Story 1.4

**Story 1.4 Impact:**
- README.md creation task needs correction (remove ITI-8, clarify Phase scope)
- No other subtasks affected
- Story remains "Approved" status with minor documentation update

### Future Epics Analysis

| Epic | Current State | Impact | Changes Needed |
|------|--------------|--------|----------------|
| **Epic 2** (Mock IHE Endpoints) | Correct - focuses on PIX Add and ITI-41 | ✅ None | None |
| **Epic 3** (Template Engine) | No IHE transaction references | ✅ None | None |
| **Epic 4** (SAML & XML Signing) | No IHE transaction references | ✅ None | None |
| **Epic 5** (PIX Add Implementation) | **CORRECT** - implements ITI-44 (v3) | ✅ None | None |
| **Epic 6** (ITI-41 Document Submission) | Correct - focuses on ITI-41 | ✅ None | None |
| **Epic 7** (Integration Testing) | No specific transaction changes | ✅ None | None |

**Future Phase 2 Epics (Post-MVP):**
- Will cover ITI-45 (PIX Query v3), ITI-18 (Registry Stored Query), ITI-43 (Retrieve Document Set)
- Already planned per PRD goals: "Support comprehensive query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) in post-MVP phases"

### Epic Impact Summary
✅ **No epic structure changes required** - all epics are correctly scoped. This is purely a README documentation correction.

---

## Section 3: Artifact Conflict & Impact Analysis

### README.md (❌ NEEDS CORRECTION)

**Current Issue:**
- Acknowledgments section lists: "ITI-8 - Patient Identity Feed (PIX Add)"
- This is INCORRECT - ITI-8 is the HL7 v2 version (pipe-delimited), not implemented in this project

**Impact:**
- User confusion about which IHE transactions are supported
- Misrepresentation of project capabilities
- Inconsistency with all other project documentation

### PRD (✅ CORRECT - No Changes Needed)

**Current State:**
- Goals correctly state: "Support comprehensive query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) in post-MVP phases"
- Requirements (FR5, FR6, FR7, FR8) correctly reference PIX Add (implicitly ITI-44) and ITI-41
- Phase 2 scope correctly deferred

**Impact:** ✅ None - PRD is accurate

### Architecture Documents (✅ CORRECT - No Changes Needed)

**Verified Artifacts:**
- **ADR-001** (Hybrid MTOM Implementation): Correctly references "PIX Add (ITI-44)" and "ITI-41"
- **ADR-003** (HL7v3 Message Construction): Correctly references "IHE PIX Add (ITI-44)"
- **external-apis.md**: Correctly lists "IHE ITI TF-2b: Patient Identifier Cross-referencing HL7 V3 (ITI-44)"
- **Spike Findings 1.1, 1.3**: Correctly reference ITI-44

**Impact:** ✅ None - Architecture documentation is accurate

### Story 1.4 (⚠️ MINOR UPDATE NEEDED)

**Current State:**
- Story status: "Approved" (10/10 readiness score from PO validation)
- README creation subtask includes placeholder for acknowledging IHE transactions

**Required Change:**
- Update README creation task to specify correct transaction list (ITI-44, ITI-41 for Phase 1)

**Impact:** Minor - story remains approved, only README guidance needs clarification

### Artifact Impact Summary

| Artifact | Status | Changes Required |
|----------|--------|-----------------|
| README.md | ❌ Incorrect | Update acknowledgments section |
| Story 1.4 | ⚠️ Minor update | Clarify README requirements |
| PRD | ✅ Correct | None |
| Architecture Docs | ✅ Correct | None |
| Epic Definitions | ✅ Correct | None |
| Code Implementation | ✅ Correct | None |

---

## Section 4: Path Forward Evaluation

### ✅ Recommended Path: Direct Adjustment (Documentation Correction)

**Rationale:**
- Implementation is 100% correct (all code references ITI-44)
- Architecture documentation is accurate
- Only README.md has incorrect reference
- No scope change - just documentation clarification
- Story 1.4 is already approved and in progress

**Effort Required:** 
- 🟢 **MINIMAL** - Single file update (README.md)
- Update Story 1.4 Dev Notes to reflect clarification
- No code changes required

**Work Impact:**
- ✅ No completed work thrown away
- ✅ No rollback required
- ✅ No additional stories needed

**Risks:**
- 🟢 **NONE** - Pure documentation correction

**Timeline Impact:**
- 🟢 **ZERO** - Can be corrected immediately during Story 1.4 completion

### ❌ Option 2: Rollback
**NOT APPLICABLE** - No incorrect code to rollback

### ❌ Option 3: MVP Re-scoping
**NOT APPLICABLE** - No scope change, only documentation correction

---

## Section 5: Specific Proposed Edits

### Edit 1: README.md - Acknowledgments Section

**Location:** `README.md` (bottom of file, Acknowledgments section)

**Current Text:**
```markdown
## Acknowledgments

This project implements IHE integration profiles:
- **ITI-8** - Patient Identity Feed (PIX Add)
- **ITI-41** - Provide and Register Document Set-b
- **ITI-43** - Retrieve Document Set
- **ITI-44** - Patient Identity Feed HL7v3

For IHE specifications, see: https://profiles.ihe.net/
```

**Proposed Text:**
```markdown
## Acknowledgments

This project implements IHE integration profiles:

**Phase 1 (MVP):**
- **ITI-44** - Patient Identity Feed HL7v3 (PIX Add v3)
- **ITI-41** - Provide and Register Document Set-b

**Phase 2 (Post-MVP):**
- **ITI-45** - PIX Query v3
- **ITI-18** - Registry Stored Query
- **ITI-43** - Retrieve Document Set

For IHE specifications, see: https://profiles.ihe.net/
```

**Rationale:**
- Removes incorrect ITI-8 reference
- Clarifies Phase 1 vs Phase 2 scope
- Explicitly identifies ITI-44 as "PIX Add v3" to avoid confusion
- Aligns with PRD goals and architecture documentation
- Matches actual implementation

---

### Edit 2: README.md - Overview Section (Optional Enhancement)

**Location:** `README.md` (Overview section, line 7)

**Current Text:**
```markdown
This utility enables healthcare system integrators to:
- Parse patient demographics from CSV files
- Generate HL7v3 PIX Add messages
```

**Proposed Text:**
```markdown
This utility enables healthcare system integrators to:
- Parse patient demographics from CSV files
- Generate HL7v3 PRPA_IN201301UV02 messages for PIX Add (ITI-44)
```

**Rationale:** (Optional - adds technical specificity for clarity)

---

### Edit 3: Story 1.4 - Dev Notes Section

**Location:** `docs/stories/1.4.project-structure-dependencies.md` (Dev Notes section)

**Add to README Structure subsection:**

```markdown
**IHE Transaction References in README:**
- Phase 1 (MVP): ITI-44 (PIX Add HL7v3), ITI-41 (Provide and Register Document Set-b)
- Phase 2 (Post-MVP): ITI-45 (PIX Query v3), ITI-18 (Registry Stored Query), ITI-43 (Retrieve Document Set)
- DO NOT include ITI-8 (PIX Add v2) - this project implements HL7v3 (ITI-44), not HL7 v2 (ITI-8)
```

**Rationale:** Provides clear guidance for Dev Agent implementing README creation

---

## Section 6: PRD MVP Impact

### MVP Scope Status
✅ **NO CHANGES TO MVP SCOPE**

**Current MVP Scope (Confirmed):**
- Epic 1: Foundation & CSV Processing ✅
- Epic 2: Mock IHE Endpoints ✅
- Epic 3: Template Engine & CCD Personalization ✅
- Epic 4: SAML Generation & XML Signing ✅
- Epic 5: PIX Add Transaction Implementation (ITI-44) ✅
- Epic 6: ITI-41 Document Submission & Complete Workflow ✅
- Epic 7: Integration Testing & Documentation ✅

**Post-MVP / Phase 2 Scope (Confirmed):**
- ITI-45 (PIX Query v3)
- ITI-18 (Registry Stored Query)
- ITI-43 (Retrieve Document Set)
- XCPD (Cross-Community Patient Discovery)

### PRD Goals Alignment
✅ All PRD goals remain unchanged and aligned:
- ✅ FR5: "System shall construct HL7v3 PRPA_IN201301UV02 patient registration messages" - This IS ITI-44
- ✅ Post-MVP: "Support comprehensive query/retrieve workflows (PIX Query, XCPD, ITI-18, ITI-43) in post-MVP phases"

---

## Section 7: High-Level Action Plan

### Immediate Actions (During Story 1.4 Completion)

1. **Update README.md** (Dev Agent)
   - Replace Acknowledgments section with corrected transaction list
   - Clarify Phase 1 vs Phase 2 scope
   - Remove ITI-8 reference

2. **Update Story 1.4 Dev Notes** (Scrum Master - Bob)
   - Add clarification about correct IHE transaction references
   - Document this change proposal in story Change Log

3. **Complete Story 1.4 QA** (QA Agent)
   - Verify README.md has correct transaction references
   - Confirm no ITI-8 references remain
   - Approve story completion

### No Additional Stories Required
✅ This correction is handled within Story 1.4 scope (README creation task)

### No Epic Changes Required
✅ All epics remain as currently defined

---

## Section 8: Agent Handoff Plan

### Primary Agent: Dev Agent (Currently Working Story 1.4)
**Responsibility:** Implement README.md corrections during Story 1.4 completion

### Supporting Agent: QA Agent
**Responsibility:** Validate README.md has correct transaction references during QA review

### Scrum Master (Bob): This Proposal
**Responsibility:** Document change analysis and obtain user approval

### No PM or Architect Involvement Required
✅ No fundamental replanning needed - documentation correction only

---

## Section 9: Change-Checklist Completion Summary

| Checklist Section | Status | Key Findings |
|-------------------|--------|--------------|
| **1. Trigger & Context** | ✅ Complete | QA review discovered ITI-8 vs ITI-44 documentation inconsistency |
| **2. Epic Impact** | ✅ Complete | No epic changes required - all epics correctly scoped |
| **3. Artifact Conflicts** | ✅ Complete | Only README.md needs correction - all other docs correct |
| **4. Path Forward** | ✅ Complete | Direct Adjustment recommended - minimal effort, zero risk |
| **5. Sprint Change Proposal** | ✅ Complete | This document with specific edits |

---

## Section 10: Approval & Next Steps

### Required User Approval

**User, please confirm:**

1. ✅ README.md should list **ITI-44** (PIX Add HL7v3), not ITI-8 (PIX Add v2)
2. ✅ Phase 1 (MVP) includes: ITI-44 and ITI-41 only
3. ✅ Phase 2 (Post-MVP) includes: ITI-45, ITI-18, ITI-43
4. ✅ Proposed README edits are accurate and complete
5. ✅ No epic or story restructuring required

### Upon Approval

1. Scrum Master (Bob) updates Story 1.4 Dev Notes with clarification
2. Dev Agent implements README.md corrections during Story 1.4 completion
3. QA Agent validates corrections during final QA review
4. Story 1.4 proceeds to completion with corrected documentation

---

## Appendix: Search Results Summary

**ITI-8 References Found:** 2 occurrences
- `docs/stories/1.1.soap-mtom-integration-spike.md` - Reference URL comment (ITI-44/ITI-8)
- `docs/stories/1.3.hl7v3-message-construction-spike.md` - Reference URL comment (ITI-44/ITI-8)

**Note:** These references are in comments noting the IHE specification URL format, NOT claiming to implement ITI-8.

**ITI-44 References Found:** 51 occurrences across documentation - ALL CORRECT

**Conclusion:** Entire codebase and documentation correctly implements and references ITI-44 (HL7v3), except for single incorrect README.md acknowledgments section.

---

**End of Sprint Change Proposal**
