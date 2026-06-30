# Multi-Source Candidate Data Transformer — Design

## How I broke down the pipeline
The brief gave a dummy pipeline shape, so I restructured it slightly to match how I
actually built it:

ingest -> extract -> normalize -> reconcile -> reshape -> verify

- **ingest**: figure out what's being fed in (CSV path, list of GitHub URLs) from CLI flags.
- **extract**: each source has its own parser that reads the raw input and returns a flat
  list of "raw records" — one per person it found, tagged with which source it came from.
  No parser is allowed to crash the whole run; bad rows/responses get skipped and logged.
- **normalize**: independent, testable functions that clean up individual values — phone
  numbers into E.164, dates into YYYY-MM, skill names into a canonical form, countries
  into ISO-3166 codes. Each one either succeeds or fails explicitly; nothing gets guessed.
- **reconcile**: this is the merge step — group all the raw records into one record per
  real person, and for every field, decide what the "true" value should be when sources
  disagree, while also scoring how confident I am in that decision.
- **reshape**: take the internal canonical record and project it into whatever shape a
  runtime config asks for — picking fields, renaming them, applying different
  normalization, deciding what to do with missing values.
- **verify**: validate the reshaped output against a schema generated from that same
  config, right before it's returned, so nothing malformed ever leaves the pipeline.

## Output schema and the formats I picked
I kept the canonical schema as given — candidate_id, full_name, emails[], phones[],
location, links, headline, years_experience, skills[], experience[], education[],
provenance[], overall_confidence.

For formats: phone numbers go through Python's `phonenumbers` library and come out as
E.164 strings; dates are normalized to YYYY-MM; countries map to ISO-3166 alpha-2 codes
through a small lookup table; skills go through a canonical lookup dictionary so things
like "js" and "JavaScript" collapse into one name — if a skill isn't in my dictionary I
don't drop it, I just title-case it and mark it with lower confidence, since an unknown
skill is still real information, just less standardized.

## How I match and merge candidates across sources
I match people primarily by normalized email — lowercased and trimmed — since that's the
most reliable unique identifier I have from the structured source. GitHub doesn't give
me an email at all, so anything coming from GitHub falls back to matching on normalized
full name against people I've already grouped from email-based sources; if there's no
match at all, it just becomes its own record.

For resolving conflicting values, I didn't want to silently pick a winner and hide the
disagreement. For array-style fields like emails and phones, I keep every distinct value
I find across sources instead of overwriting — and I lower the confidence score on that
field when there's a genuine conflict, since "I have two phone numbers and I'm not sure
which is current" is more honest than confidently presenting one.

For fields where I do need to pick a single winner — like full_name — I lean on whichever
source gave me a more complete value rather than arbitrarily picking the first one I see.

I also gave structured and unstructured sources different default trust levels depending
on the field: the recruiter CSV is more reliable for things like phone numbers and
current job title, since that's data a recruiter has presumably verified directly, while
GitHub is more reliable for skills and headline/bio, since that's closer to the
candidate's own self-reported signal. I didn't want this bias to be permanently hardcoded
though, so I added a config option (`field_priority`) that lets the runtime config
override which source wins for a specific field — so the same merge engine can be told
"actually, trust GitHub over the CSV for phone numbers this time" without touching code.

Confidence per field comes from: a base score depending on whether the contributing
source is structured (0.9) or unstructured (0.7), a small bonus if multiple sources agree
on the same value, and a penalty if they genuinely conflict. The overall_confidence for a
candidate is just the average of all the field-level confidence scores I actually
populated — so a candidate found in only one weak source still gets a record, just with a
visibly lower confidence rather than being excluded or faked into looking trustworthy.

## How the runtime config works
I kept a hard separation between my internal canonical model and what actually gets
returned. The canonical record gets built once, completely, regardless of what the
caller eventually wants. A separate projection step then reads the config and reshapes
that record — selecting only the requested fields, remapping/renaming them via a "from"
path, reapplying a different normalization if the config asks for one, and deciding what
happens to missing values based on an `on_missing` setting (null it, omit it entirely, or
raise an error if it's a required field). Validation always runs after this projection
step, against a schema built dynamically from that same config — never against my
internal model — so the thing I'm validating is exactly the thing I'm about to return.

## Edge cases I specifically handled
1. A candidate shows up in only one weak source — I still emit a record for them, just
   with a lower overall_confidence, rather than dropping them entirely.
2. A GitHub URL that 404s, hits a rate limit, or times out — that source just returns
   nothing for that person, logs why, and the rest of the batch keeps processing normally.
3. A CSV row with no name and no email at all — there's nothing to identify that person
   by, so I skip the row with a logged reason rather than letting it corrupt a record.
4. Two structured sources disagree on a phone number for what's clearly the same person —
   I keep both values rather than guessing, and the confidence score reflects the
   disagreement.
5. A phone number or date string that doesn't parse cleanly — I drop it rather than
   guess, and record a provenance entry with method "failed_normalize" so it's clear the
   value was attempted but rejected, not just silently missing.

## What I deliberately left out, given the time I had
- LinkedIn parsing — there's no public API for it and scraping would violate their terms
  of service, so I didn't touch it.
- Resume PDF/DOCX parsing — I used GitHub as my required unstructured source instead,
  since it's a real public API I could integrate cleanly in the time available.
- Any kind of fuzzy or ML-based name matching across sources — I'm doing exact
  normalized-email matching with a simple normalized-name fallback, which is good enough
  for this dataset size but wouldn't scale well to, say, two people who share a name and
  have no email overlap.