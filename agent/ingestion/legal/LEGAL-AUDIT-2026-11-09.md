# Legal source audit, 2026-11-09

This is an agent audit of public official sources, not human proofreading, independent legal advice, or child-safety review. The added PDFs are preserved without modification. Only the three authored cards listed below enter the corpus; downloading a law does not make every provision an ingested document.

## Findings and admission decisions

| Instrument | Primary evidence opened | Result | Corpus treatment |
|---|---|---|---|
| ND80/2017 | [Government identity page](https://chinhphu.vn/default.aspx?docid=190430&pageid=27160), existing signed original | Identity, issue date 17 July 2017 and original effective date 5 September 2017 confirmed. National legal database property pages return HTTP 403. [Government briefing of 4 November 2026](https://media.chinhphu.vn/bao-luc-hoc-duong-khong-bao-che-khong-chi-xu-ly-noi-bo-102261104142652522.htm) says amendments are being researched/proposed; this corroborates ongoing relevance, but does not certify the complete legal status. | Existing source ID and excerpt untouched. Current-status registry confirmation and human transcription review remain OPEN. |
| Child Law 102/2016, consolidation 108/VBHN-VPQH | [Government identity page](https://vanban.chinhphu.vn/?docid=215227&pageid=27160), attached 40-page text | Consolidation issued 27 August 2025; first page lists amendments including the one effective 1 January 2026. Article 1 means under 16, not every person under 18. Articles 6(11), 21 and 51 were read from text. This is the latest primary consolidation located in this audit, not an assertion that no later amendment exists. | New revision ID `vn-luat-tre-em-vbhn108-2025`, two explicitly authored summaries. Old unverified ID remains unchanged and unused. |
| TT06/2019 | [Government identity page](https://vanban.chinhphu.vn/?classid=1&docid=196910&pageid=27160), attached six-page scan | Issued 12 April 2019; original effective date 28 May 2019. Agent visually inspected PDF pp1 and 4. Article 6 is affected by TT03/2026. | Original candidate ID remains excluded. No stale teacher-duty text is copied into the new cards. |
| TT03/2026 | [Government page and signed PDF](https://xaydungchinhsach.chinhphu.vn/toan-van-thong-tu-03-2026-tt-bgddt-quy-dinh-quy-tac-ung-xu-cua-nha-giao-119260205093856491.htm) | Agent visually read Article 5(3)-(4), PDF p3, and Article 15(1)-(2), p7. Effective 30 January 2026; Article 6 of TT06/2019 expires. It does not repeal TT06 wholesale. | New source ID `vn-tt-03-2026-bgddt`, one authored summary with exact clause locators. |
| Intellectual Property Law, consolidation 160/2026/VBHN-LQ-VPQH | [Official Gazette identity](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-160-2026-vbhn-lq-vpqh-470657.htm), direct official PDF in table below | Issued 29 September 2026. Article 15(2), PDF p14 / printed Gazette p15, excludes legal normative texts from copyright protection. Read from the official text after checking earlier consolidation 155/2025. | Basis for legal-text reuse is now primary-source verified. It does not license portal commentary, photographs, translations by third parties or their page layouts. |

The Gazette landing page for 108/2025 displays a placeholder effective date of 01/01/1900; that value is not used as legal evidence. Initial Gazette download proxy links returned 502/timeouts. Direct PDFs were followed only from official landing-page attachment/embed URLs, without bypassing access controls. TT03 has duplicate PDF /Info dictionary keys reported by pypdf; the original bytes are preserved, and visual inspection was used for the cited provisions.

## Preserved official originals

| File | Pages | SHA256 | Official download |
|---|---:|---|---|
| [original/nd-80-2017-nd-cp.signed.pdf](original/nd-80-2017-nd-cp.signed.pdf) | 8 | `cdede8a6aa3fec59064f795483f937d179d0d6f37d9acee6914fa9bf6937a8e4` | [official PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2017/07/80.signed.pdf) |
| [original/luat-tre-em-108-vbhn-vpqh-2025.pdf](original/luat-tre-em-108-vbhn-vpqh-2025.pdf) | 40 | `97ba73c1f8cd155dbeca5d96e9dc993b8410f4bffe60592f443ca8039735c0ed` | [official PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/9/108-vbhn-vpqh.pdf) |
| [original/tt-06-2019-bgddt.signed.pdf](original/tt-06-2019-bgddt.signed.pdf) | 6 | `b46a431a38d484e7c97ff4c7ff46f30b514312f331e1125066659287323e1194` | [official PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2019/05/06-bgddt.signed.pdf) |
| [original/tt-03-2026-bgddt.signed.pdf](original/tt-03-2026-bgddt.signed.pdf) | 7 | `84d4f7fc55d75d32d378b7f21f718c717365729b1f2cbbe08c6fb60431169e24` | [official PDF](https://xdcs.cdnchinhphu.vn/446259493575335936/2026/2/5/03-2026-tt-bgddt-signed-786b2-17702586471691873326971.pdf) |
| [original/ip-law-155-vbhn-vpqh-2025.pdf](original/ip-law-155-vbhn-vpqh-2025.pdf) | 134 | `313f5aec815cc110e90bc8a461f8ea05e3bed818a24b8278f48065b1483a0dbb` | [official PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/9/155-vbhn-vpqh.pdf) |
| [original/ip-law-160-vbhn-lq-vpqh-2026.pdf](original/ip-law-160-vbhn-lq-vpqh-2026.pdf) | 140 | `53aed7cc50684a239e4fc04c6687a9df8071cf7ff557cce924eb258d2cfe4378` | [official PDF](https://congbaocdn.chinhphu.vn/180507251028987904/2026/10/6/470657-1791273236_v1_1791273883_signed.pdf) |

## New substantive cards and limits

- `kb-legal-rieng-tu-duoi16`: privacy and disclosure-consent provisions, with the under-16 boundary and an explicit warning that it is not a complete data-processing rule.
- `kb-legal-bao-tin-xam-hai`: reporting responsibilities, reception/verification and the statutory national-hotline provision. It does not invent a telephone number, filing deadline, local directory or guaranteed outcome.
- `kb-school-nha-giao-tt03-2026`: teacher listening/support duties, reporting discovered violence/abuse, unlawful disclosure prohibition and the precise TT06 partial-repeal relation.

All three separate statutory summaries from SafeVoice practical suggestions. Each has claim-level `_review` notes recording agent-only checking and PENDING human review. No existing authored card, original ND80 excerpt, source record, benchmark label or historical corpus version was modified. No padding, repeated paragraphs or manufactured source endorsements were added.

Old source metadata still describes the earlier audit and is immutable for old citations; these findings are recorded separately, and new admissions use distinct IDs. There are now 15 registry candidates: three `open_reuse`, one `authored`, four `reference_only`, seven `unverified`. Four usable sources still miss the six-source target. The corpus has 57 documents / 80 chunks, far below 350; these targets remain unmet.

Review work remaining is explicit in [HUMAN-REVIEW-CHECKLIST.md](HUMAN-REVIEW-CHECKLIST.md). No row has been signed by a human. An agent reading a PDF is not such a signature.
