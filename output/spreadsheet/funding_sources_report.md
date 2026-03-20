# Funding Source Extract Report

## Inputs

- companies.csv: `/Users/ej/Downloads/문서/VC_Fundraising/Folk_Top 100 Web3 Grants_2026_03_08/companies.csv`
- notes.csv: `/Users/ej/Downloads/문서/VC_Fundraising/Folk_Top 100 Web3 Grants_2026_03_08/notes.csv`
- workbook: `/Users/ej/Downloads/프로젝트/VC_Grants/VC_Fundraising0/2026-03-06__VC_Fund_Raising_Tracker_221150.xlsx`

## Source Facts

- Folk companies rows: 90
- Excel grants rows parsed: 101
- Excel accelerator rows parsed: 96
- Excel active VC rows parsed: 98
- notes.csv rows: 0
- Combined deduped records: 377

## Overlap

- Folk vs Excel grant organization overlap: 14 / 90 Folk orgs, 75 Excel orgs
- Folk vs Excel grant program overlap: 5 / 90 Folk programs, 98 Excel programs
- Folk-only organization examples: 01 exchange, 1inch, 3327, acala network, akash, aurora, axelar network, aztec network, balancer finance, biconomydao, bitdao, boba network
- Excel-only organization examples: algorand foundation, aptos foundation, arbitrum / uniswap, arbitrum foundation, arweave, assemble.io, bahamut, balancer, base, base team, binance, bioprotocol

## Deduped Mix

- accelerator: 92
- grant: 186
- vc_cohort: 1
- vc_fund: 98

## Source Mix

- excel_accelerators: 93
- excel_grants: 99
- excel_vc: 98
- folk_companies: 90

## Review Required

- flagged rows: 24
- 2048 | 2048 | excel_accelerators | program cell is numeric-like and needs review
- 500 | 500 | excel_accelerators | program cell is numeric-like and needs review
- a16z | Speedrun | excel_accelerators | organization inferred from url
- Antropic | Antropic grants | excel_accelerators | missing url
- Bahamut | Bahamut Foundation Grants | excel_grants | missing official url
- Base | Base Builder Grants | excel_grants | missing official url
- Base | BaseCamp Awards | excel_grants | missing official url
- Btv | The Mint | excel_accelerators | organization inferred from url
- Eranyc | Founders Fellowship | excel_accelerators | organization inferred from url
- Ethereum Foundation | Ethereum Ecosystem Support Program | excel_grants | missing official url
- Fi | Founder Institute | excel_accelerators | organization inferred from url
- Immutable | Immutable zkEVM Grants | excel_grants | missing official url
- Interchain Foundation | Interchain Foundation Grants | excel_grants | missing official url
- Iterative Incubator | Iterative Incubator (AI dev tools) | excel_accelerators | missing url
- Joinef | Entrepreneur First | excel_accelerators | organization inferred from url
- LAUNCH | LAUNCH | excel_accelerators | missing url
- Menlovc | Menlo Ventures X Anthropic | excel_accelerators | organization inferred from url
- Mozilla AI Accelerator | Mozilla AI Accelerator (Open source local AI) | excel_accelerators | missing url
- Oasis | Oasis Ecosystem Grants | excel_grants | missing official url
- Outlierventures | Outlier | excel_accelerators | organization inferred from url

## Recommended Update Path

- Use the generated `companies`-style CSV when you want a familiar CRM-like flat table.
- Use the normalized CSV when updating `Organization -> Program -> Opportunity` records in the repo.
- Review flagged accelerator rows before importing them into canonical seed data.
- `notes.csv` is currently empty, so it does not add useful enrichment yet.
