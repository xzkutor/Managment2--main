# ADR-0012: Explicit Product Match Decisions and Review Surfaces

- Status: Accepted
- Date: 2026-03-24
- Related: ADR-0001 DB-first architecture for comparison and review flows; ADR-0002 Persist confirmed mappings; keep candidate matches runtime-only

## Context

The current comparison workflow already separates persisted product mappings from runtime heuristic suggestions, but it still has three operator-facing gaps:

1. an operator can confirm a pair but cannot explicitly reject a pair that looks strong heuristically yet is still wrong;
2. an operator can only choose from the heuristic shortlist and cannot manually select another target product from the currently reviewed comparison scope;
3. there is no dedicated review surface for existing confirmed product mappings.

The project already has the necessary persistence primitive for pair-level review decisions:

- `ProductMapping` with unique `(reference_product_id, target_product_id)` semantics;
- `match_status` on the mapping row;
- repository update/create behavior for the same pair.

The comparison domain therefore needs a decision on how explicit review outcomes are represented and how they affect future comparison results.

## Decision

### 1. Product-pair review is explicit and durable

Operator review is an explicit decision over one exact pair:

- `reference_product_id`
- `target_product_id`

The supported durable decisions in this wave are:

- `confirmed`
- `rejected`

These decisions are persisted in `ProductMapping.match_status`.

### 2. `rejected` is a pair-level suppression decision

`rejected` means that one exact reference-target pair has been reviewed and must not be proposed again by comparison.

`rejected` is scoped only to that pair.

It does **not**:

- reject the whole reference product;
- globally blacklist the target product for all other reference products;
- act as authoritative positive truth.

### 3. Confirmed mappings remain the only authoritative positive relation

Only `match_status="confirmed"` is authoritative persisted cross-store truth.

`match_status="rejected"` is durable review history plus a suppression rule. It affects future comparison behavior but is not a positive mapping that downstream business logic may treat as cross-store equivalence.

This preserves ADR-0002.

### 4. A later confirm may override a prior reject for the same pair

If an operator later decides that a previously rejected exact pair should in fact be accepted, the system may update the same persisted pair record from `rejected` to `confirmed`.

The inverse is also allowed: a previously confirmed exact pair may be changed to `rejected` if operator review determines that the persisted relation was wrong.

The durable state belongs to the pair, and the latest explicit operator decision governs future behavior.

### 5. Manual target selection is allowed within the selected target-category scope

During comparison review, the operator may confirm not only a heuristic candidate but also any eligible target product from the currently selected target categories.

The initial manual picker scope is therefore:

- bounded to the selected target categories used in the current comparison request;
- not expanded to the entire target store catalog.

### 6. The current one-target-per-confirmed-pair rule remains in force in this wave

If the current system prevents a target product from being confirmed for more than one reference product, that invariant remains in force for:

- heuristic confirmation;
- manual confirmation via searchable dropdown;
- confirmed-pairs review semantics.

This ADR does not introduce one-to-many or many-to-one confirmed product mappings.

### 7. Confirmed mappings require a dedicated review page

The system shall provide a separate operator-facing page for viewing persisted confirmed product mappings.

This page is distinct from the runtime comparison page and is the canonical review surface for already persisted positive mappings.

The first iteration of this page is read-only.

## Rationale

### Why use `ProductMapping.match_status`

The project already has the correct persistence anchor for exact-pair review. Reusing `ProductMapping` avoids introducing a second table before separate lifecycle or audit requirements are proven.

### Why reject is pair-level

The reported false positive problem is about one specific reference-target pair that the heuristic scores highly despite important real-world differences. A broader rejection scope would suppress too much and would create avoidable false negatives.

### Why confirm remains the only positive truth

The system needs a clear distinction between:

- durable authoritative mapping used by downstream logic;
- durable negative review used only to suppress future proposals.

Treating only `confirmed` as positive truth keeps the persistence model understandable and consistent with ADR-0002.

### Why allow manual selection from selected categories only

Operators need more than the heuristic shortlist, but the workflow should remain bounded to the active comparison scope. Restricting manual search to the selected target categories balances operator flexibility with predictable review boundaries.

### Why keep the current uniqueness-style review rule

Changing one-target-per-confirmed-pair semantics in the same wave would enlarge both domain and migration scope. The present change is about review controls and review surfaces, not about redefining the confirmed mapping cardinality model.

## Consequences

### Positive

- operators can explicitly reject false-positive heuristic pairs;
- rejected pairs do not reappear in later comparison runs;
- operators can confirm a correct target product even when the heuristic shortlist misses it;
- persisted confirmed mappings gain a dedicated review surface;
- the design extends the current model without adding a new persistence subsystem.

### Negative

- comparison semantics become more complex because persisted rejections must be consulted during result construction;
- the UI must clearly distinguish persisted confirmed mappings from runtime high-confidence suggestions;
- manual selection adds API and frontend-state complexity.

## Operational implications

The comparison service must honor persisted `rejected` rows as pair-level suppression rules during:

- high-confidence heuristic suggestion generation;
- ambiguous candidate-group construction;
- manual eligible-target lookup for a given reference product.

The confirmed-pairs page must display only persisted mappings, not runtime-only heuristic suggestions.

## Non-goals

This ADR does not:

- introduce full decision history or audit-log infrastructure;
- allow manual search across the entire target store catalog;
- change confirmed mapping cardinality semantics;
- add bulk confirm/reject workflows.

## Alternatives considered

### Keep reject as a transient UI-only action

Rejected because the same false-positive pair would reappear after each comparison run.

### Create a separate rejected-pairs table

Rejected for this wave because existing `ProductMapping` already provides the required pair key and state field.

### Allow manual target selection across the whole target store

Rejected for this wave because it weakens category-scoped comparison boundaries and broadens the review contract more than necessary.

### Introduce many-to-one confirmed mappings in the same wave

Rejected because it is a separate domain decision and would materially expand the scope beyond review workflow improvements.

## Review trigger

Revisit this ADR if any of the following become true:

- confirmed mappings need many-to-one or one-to-many semantics by design;
- the project requires immutable decision history separate from current pair status;
- operators need manual target search across the entire target store rather than selected target categories only.
