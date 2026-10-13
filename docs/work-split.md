### **Samhita: Real Data and Architecture**

* Research ClinicalTrials.gov API and AACT datasets to identify available trial, site, location, recruitment status, and date fields.  
* Extract a sample of 20–30 clinical trials with associated sites.  
* Document which site activation fields are publicly available versus missing.  
* Create the high-level system architecture diagram, including data flow, database, backend, frontend, and future LLM integration.  
* Write the Architecture and Technical Stack sections of the technical specification.

# **TrialFlow: Data Research and System Architecture**

**Contributor:** Samhita  
**Course:** CS 146S, Autumn 2026  
**Date:** October 13, 2026

## **Work Completed**

### **1\. Clinical Trial Data Research**

Researched ClinicalTrials.gov API v2 and the AACT relational database to identify available clinical trial, facility, recruitment status, and date fields.

Selected ClinicalTrials.gov API v2 as TrialFlow's primary data source because it provides structured public study records without requiring a separate database download.

### **2\. Real Clinical Trial Data Extraction**

Developed and executed a Python extraction script using the ClinicalTrials.gov API.

Successfully retrieved:

* 25 real breast cancer clinical trials.  
* 1,715 associated reported site records.  
* Original API responses in JSON format.  
* Metadata documenting the extraction date, query, and record counts.

The dataset contains trials with recruiting or not-yet-recruiting statuses, selected by most recent registry update.

### **3\. Public Data Limitations**

Documented the difference between publicly available clinical trial information and internal site activation data.

ClinicalTrials.gov provides study identifiers, facility locations, recruitment statuses, and reported dates.

Internal milestones such as IRB approval, contract execution, budget finalization, staff training, and pharmacy readiness are not available as complete structured site-level records.

For the MVP, TrialFlow will use real trial and site data alongside clearly labeled synthetic activation milestones.

### **4\. System Architecture**

Designed the proposed system architecture and data flow:

ClinicalTrials.gov API → Python Data Ingestion → PostgreSQL Database → FastAPI Backend → Next.js/React Frontend.

The backend will calculate site readiness, track milestone dependencies, and identify blockers using deterministic rules.

A future LLM component will provide explanations and suggested next actions based on stored site records.

### **5\. Technical Stack**

Selected the proposed development stack:

* Python and Requests for ingestion.  
* PostgreSQL for structured data storage.  
* FastAPI for backend APIs.  
* SQLAlchemy and Pydantic for database access and validation.  
* Next.js, React, and TypeScript for the frontend.  
* pytest and Playwright for testing.

## **Deliverables**

1. trials.csv: 25 real clinical trials.  
2. sites.csv: 1,715 associated site records.  
3. raw\_25\_studies.json: original API response data.  
4. sample\_metadata.json: retrieval information and counts.  
5. Architecture diagram and written Architecture section.  
6. Technical Stack section.  
7. Research documenting public versus missing operational data.

## **Next Steps**

Integrate the dataset into TrialFlow's database, add synthetic site activation milestones, and implement the readiness and blocker tracking workflows.

The architecture and technology choices are proposed for the MVP. Full application implementation remains future work.

## **Samhita's Deliverables: Data Research and Architecture**

1. **architecture.md**  
   * Research on ClinicalTrials.gov API and AACT datasets.  
   * Documentation of publicly available versus missing site activation fields.  
   * High-level system architecture diagram showing data flow, database, backend, frontend, and future LLM integration.  
   * Written Architecture and Technical Stack sections.  
2. **trials.csv**  
   * Contains 25 real clinical trials retrieved from ClinicalTrials.gov.  
   * Includes trial identifiers, titles, recruitment statuses, and study dates.  
3. **sites.csv**  
   * Contains 1,715 associated site records.  
   * Includes facility names, geographic locations, and links to their respective clinical trials.  
4. **raw\_25\_studies.json**  
   * Contains the original, unprocessed API responses for the 25 clinical trials.  
   * Preserves the complete retrieved study records for reference and verification.  
5. **sample\_metadata.json**  
   * Documents the API query, retrieval timestamp, selection criteria, and dataset counts.  
   * Records the extraction results to support reproducibility.

### 

### 

### 

### 

### **Keyi: Synthetic Data and API Design**

* Research standard clinical trial site activation milestones, dependencies, and typical delays.  
* Define the database schema for trials, sites, milestones, task owners, deadlines, and dependencies.  
* Generate labeled synthetic activation data for 10–20 sites.  
* Design key API endpoints with example request and response formats.  
* Write the API Design and Business Context sections of the technical specification, including measurable success metrics.


# **TrialFlow: Synthetic Data, Database Schema, and API Design**

**Contributor:** Keyi  
**Course:** CS 146S, Autumn 2026  
**Date:** October 13, 2026

## **Work Completed**

### **1\. Site Activation Research**

Researched standard clinical trial site activation milestones, their dependencies, and typical delays, using industry sources (Tufts CSDD, ACRP, CASRAI, Advarra, WCG, and others).

Defined a standard checklist of 10 milestones across regulatory, contracts, pharmacy, training, operations, and activation workstreams: IRB approval, contract executed, budget finalized, regulatory documents, staff training, pharmacy setup, lab and systems access, drug shipped and received, site initiation visit (SIV), and green light.

Identified contracts, budgets, and IRB review as the most common sources of delay. These will drive the synthetic delay scenarios.

### **2\. Real Data Verification and Field Mapping**

Verified every real-data field against the raw ClinicalTrials.gov API v2 responses (25 trials, 1,715 locations), and produced a mapping table from API v2 JSON paths to TrialFlow database columns.

Flagged data-quality issues that affect the design:

* API v2 locations have no stable ID, so sites are de-duplicated by name, city, state, and country.  
* 715 locations use placeholder names ("Research Site", "Research Facility"). These are never merged, which prevents 100 groups of different sites from being wrongly combined. The result is 1,662 unique sites and 1,715 trial sites.  
* Trial phases are arrays (e.g. Phase 1 and Phase 2), some dates are partial (year and month only), and coordinates are city-level rather than facility-level.  
* The sample contains no not-yet-recruiting sites, so sites in start-up will be a clearly labeled synthetic subset.

### **3\. Database Schema**

Designed the final database schema: 9 tables covering trials, sites, trial sites, users (task owners), milestone templates, template dependencies, milestones, milestone dependencies, and milestone change history.

Integrated Samhita's architecture decisions:

* Adopted her `source_type` provenance label (`public_registry` or `synthetic`) on every record.  
* Kept reported recruitment status separate from activation status, so activation is never inferred from the registry.  
* Replaced a stored blockers table with blockers computed at query time.

Enforced the key rules in the database where possible:

* No duplicate trial sites.  
* No self-dependencies or duplicate dependencies.  
* Dependencies must stay within one trial site.  
* Completion and activation dates must match their status.

Rules the database cannot express, such as no dependency cycles, are assigned to the backend service layer.

Implemented the schema as SQLAlchemy models.

### **4\. API Design**

Designed 11 REST endpoints covering trials, the trial site dashboard, milestone details, the dependency graph, milestone updates, dependency management, the change-history timeline, templates, and users.

Wrote example request and response JSON for the three most important endpoints:

* The trial dashboard: readiness %, top blocker, and next-action owner for each site.  
* The dependency graph, with blocking flags.  
* The milestone update, which records every status, owner, or due-date change in the history.

Built Pydantic schemas and FastAPI stub endpoints that return placeholder data, so the full API can be explored on the auto-generated `/docs` page.

### **5\. Testing**

Wrote 27 automated pytest tests. They confirm the models can be created, the database rejects invalid data (duplicate trial sites, self-dependencies, cross-site dependencies, invalid statuses), and every API endpoint responds as designed.

## **Deliverables**

1. site-activation-research.md: milestones, dependencies, and delay benchmarks.  
2. data-mapping.md: API v2 field mapping and data-quality flags.  
3. schema.md: final database schema, rules, and computed values.  
4. api-design.md: endpoint table and example requests and responses.  
5. Backend skeleton: SQLAlchemy models, Pydantic schemas, and FastAPI stub endpoints.  
6. Automated tests: 27 passing pytest tests.  
7. CLAUDE.md: project context and conventions for ongoing development.

## **Next Steps**

* Generate labeled synthetic activation data for 10–20 sites, including on-track, IRB-delay, and contract-stall scenarios.  
* Write the API Design and Business Context sections of the technical specification, including measurable success metrics.

Connecting the API to the database and implementing the readiness, blocker, and dependency-cycle logic remain future work.

## **Keyi's Deliverables: Synthetic Data and API Design**

1. **site-activation-research.md**  
   * Standard site activation milestones, typical owners, and dependencies.  
   * Benchmark timelines and common causes of delay.  
2. **data-mapping.md**  
   * Mapping from ClinicalTrials.gov API v2 fields to TrialFlow database columns.  
   * Flags for missing, array, and unreliable fields, and the site de-duplication rule.  
3. **schema.md**  
   * Final database schema with keys, constraints, and business rules.  
   * The values computed at query time, and how the schema reconciles with Samhita's architecture.  
4. **api-design.md**  
   * Endpoint table with methods, paths, purposes, and query parameters.  
   * Example request and response JSON for the three most important endpoints.  
5. **backend/**  
   * SQLAlchemy models, Pydantic schemas, and FastAPI stub endpoints.  
   * pytest tests that verify the models and the database constraints.
