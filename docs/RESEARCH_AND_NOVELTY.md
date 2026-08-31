# Research and Prior-Art Note

**Prepared by Supreet Gandolli — 28 August 2026**

This is a technical research note, not a legal patentability opinion. A patent professional should run a jurisdiction-specific claim search before filing.

## Current research baseline

The closest recent academic work is Li, Du, and Wang, **“LLM-Driven Estimation of Personal Carbon Footprint from Dialogues,”** ClimateNLP 2025, pp. 278–287, DOI `10.18653/v1/2025.climatenlp-1.20`. Their Progressive Contextual Carbon Tracking (PCCT) system combines knowledge-guided activity extraction, structured memory across dialogue turns, and emission-factor retrieval. It introduces CarbonDialog-1K: 1,028 annotated multi-turn conversations across seven regions and six activity categories. This substantially weakens any novelty claim based only on conversational/free-text carbon estimation.

Primary sources:

- Paper: https://aclanthology.org/2025.climatenlp-1.20/
- Dataset/code reference: https://github.com/shuqinlee/Chat2CarbonFootprint

Other relevant 2024 work includes Jasmy, Ismail, and Aljneibi, **“A novel approach to sustainable behavior enhancement through AI-driven carbon footprint assessment and real-time analytics,”** *Discover Sustainability* 5, 476 (2024), DOI `10.1007/s43621-024-00762-w`. It covers AI-supported tracking and recommendations, so generic personalized eco-recommendations are also a crowded area.

## Patent landscape sampled

- **US 12,482,004 B2**, “Carbon footprint estimation using foundation model” (IBM; priority 25 September 2023; granted 25 November 2025). Claims focus on a carbon-aware NLP foundation model using enterprise transaction, metadata, sector, geography, time, and spend data for Scope 3 estimation: https://patents.google.com/patent/US12482004B2/en
- **US 12,468,670 B2**, “Intelligent machine learning-based mapping service for footprint.” It covers weighted matching of product-component records to emission datasets, presentation of candidate records for confirmation, and creation of mappings: https://patents.google.com/patent/US12468670B2/en
- **US 11,966,956 B2**, “Measuring greenhouse gas emitting activities of a user” (priority 20 October 2020). It tracks electricity, driving, food purchases, and flights and applies CO2e coefficients to personalized activity records: https://patents.google.com/patent/US11966956B2/en
- **US 2023/0038676 A1**, “Calculating individual carbon footprints” (priority 24 August 2016; listed pending). It aggregates fragmented user-behavior data and calculates footprint/carbon-saving quantities and rewards: https://patents.google.com/patent/US20230038676A1/en
- **WO 2023/034062 A1**, “Privacy ecosystem environmental impact monitoring.” It collects ongoing activity information from user-associated devices, computes impact, proposes lower-impact changes, and can implement a control strategy after acceptance: https://patents.google.com/patent/WO2023034062A1/en
- **WO 2021/195048 A1**, “Systems and methods for determining a total amount of carbon emissions of an individual.” It infers lifestyle activities from telematics/sensor data and estimates emissions: https://patents.google.com/patent/WO2021195048A1/en
- **CN 118822575 A**, “Carbon footprint analysis method and system...” It uses an LLM to construct product life-cycle inventories and match carbon factors. It concerns product LCA rather than daily personal logs but overlaps LLM factor matching: https://patents.google.com/patent/CN118822575A/en

## Recommended novelty direction

Do **not** frame the invention as “NLP extracts activities and looks up emission factors.” The paper and patents above already occupy most of that concept.

A more defensible engineering direction is an **uncertainty-aware, India-localized clarification optimizer**:

1. Parse a log into activities, quantities, units, time, location, vehicle/fuel, occupancy, and evidence spans.
2. Produce multiple region/year-specific factor candidates with provenance and uncertainty intervals rather than silently averaging incompatible factors.
3. Estimate each missing field's expected effect on the final CO2e interval.
4. Ask only the clarification question with the greatest expected reduction in uncertainty per unit of user effort (for example, vehicle fuel may matter more than meal size).
5. Stop questioning when the result is sufficiently narrow; report the interval, assumptions, and an auditable calculation graph.
6. Learn reusable user defaults locally with privacy-preserving storage, while detecting when a new statement contradicts a stored default.

The potentially claimable center is the **selection and stopping method for clarification questions driven by propagated emissions uncertainty**, combined with factor provenance/versioning and contradiction-aware personal defaults. Each element still requires a professional prior-art and obviousness search; novelty is never guaranteed.

## Repository gap analysis

Before this contribution, the repository was a regex proof of concept despite describing an NLP model. The activity dataset was not loaded or used. Factors were averaged across vehicle and flight types without source, geography, year, boundary, or uncertainty metadata. The electricity fallback was per hour rather than per kWh, making it device-dependent and scientifically weak. The demographic average was divided by 365 without documenting the dataset provenance or confirming the original unit.

The first implementation step in this branch fixes extraction correctness, unit normalization, vehicle-fuel preservation, API validation, and calculation audit fields. Next work should replace synthetic/unsourced values with an ingestion schema containing `source`, `publication_year`, `geography`, `activity`, `unit`, `factor`, `scope_or_boundary`, `gwp_basis`, and `uncertainty`.

## Data sources to adopt

- UK DESNZ 2026 conversion factors (latest annual official release as of this note): https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting
- Central Electricity Authority, CO2 Baseline Database for the Indian Power Sector: https://cea.nic.in/tpe___cc/cdm-co2-baseline-database/?lang=en
- India BUR-4 national inventory submitted to UNFCCC: https://unfccc.int/sites/default/files/resource/India%20BUR-4.pdf
- GHG Platform India energy-sector methodology: https://ghgplatform-india.org/electricity-energy-sector/

Factors from different geographies, reporting years, scopes, and units must not be averaged without an explicit methodological justification.
