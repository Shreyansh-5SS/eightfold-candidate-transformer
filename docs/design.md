# Multi-Source Candidate Data Transformer — Design

## Pipeline
detect -> extract -> normalize -> merge -> confidence -> project-to-output -> validate

- **detect**: identify input type (CSV path, GitHub URL list) from CLI flags.
- **extract**: each source parser reads raw input, returns a list of `RawRecord` (source name + raw field dict), never raising on bad input.
- **normalize**: convert raw values into canonical formats (dates, phones, skills, country) independently and reversibly.
- **merge**: group RawRecords into one record per real person, resolve field-level conflicts, attach provenance.
- **confidence**: score each field and an overall score based on source reliability and cross-source agreement.
- **project-to-output**: apply a runtime JSON config to reshape the canonical record into the requested output shape.
- **validate**: check the projected output against a schema generated from the config before returning it.

## Canonical schema & normalized formats
Fields: candidate_id, full_name, emails[], phones[] (E.164), location{city,region,country (ISO-3166 alpha-2)}, links{linkedin,github,portfolio,other[]}, headline, years_experience, skills[{name,confidence,sources[]}], experience[{company,title,start,end (YYYY-MM),summary}], education[{institution,degree,field,end_year}], provenance[{field,source,method}], overall_confidence.

Skills are canonicalized via a lookup dictionary (e.g. "js" -> "JavaScript"); unrecognized skills are title-cased and kept at lower confidence rather than dropped.

## Merge & conflict-resolution policy
Candidates are matched primarily by normalized email (lowercased, trimmed) across sources. Records without an email (e.g. GitHub) fall back to matching on normalized full name against existing groups.

For single-value fields (name), the longest non-empty candidate wins. For array fields (emails, phones, skills), values from all sources are unioned and deduped after normalization rather than overwritten — conflicting structured values are kept side by side with reduced confidence instead of silently dropping one.

Field-type bias: structured sources (CSV/ATS) are treated as more reliable for contact/employment facts (email, phone, title, company); unstructured sources (GitHub) are treated as more reliable for skills and headline, since they reflect richer self-reported signal.

Confidence per field = base_reliability (structured 0.9, unstructured 0.7) + agreement_bonus (+0.1 if 2+ sources agree on the same normalized value) − conflict_penalty (−0.2 if sources disagree on a single-value field), clamped to [0,1]. overall_confidence is the mean of all populated field confidences; a candidate found in only one weak source still gets a record, just a low overall_confidence — never silently invented data.

## Runtime config handling
The canonical record is built once, completely, independent of any output shape. A separate projection layer reads a JSON config (field selection, "from" path remapping, per-field normalize override, include_confidence/include_provenance toggles, on_missing policy) and produces the final shape. Validation always runs against a schema generated from that same config, after projection — never against the internal canonical model.

## Edge cases handled
1. Candidate present in only one source -> still emitted, with lower overall_confidence rather than excluded.
2. GitHub URL 404s, rate-limited, or times out -> that source returns an empty list, logged, rest of the batch continues unaffected.
3. CSV row missing both name and email -> row is skipped with a logged reason, doesn't crash the file parse.
4. Two structured sources disagree on phone/email for the same matched person -> both values kept in the array field, confidence reduced, provenance shows both sources.
5. Unparseable phone/date string -> dropped from the output array (never guessed), provenance entry recorded with method="failed_normalize".

## Explicitly descoped (time constraints)
- LinkedIn profile parsing — no public API, scraping violates ToS.
- Resume PDF/DOCX parsing — GitHub used instead as the required unstructured source.
- ML/fuzzy name deduplication — exact-normalized-email matching with a simple normalized-name fallback only.