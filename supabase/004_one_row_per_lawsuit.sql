-- 004_one_row_per_lawsuit.sql — PENDING. Merge duplicate cases (same CourtListener docket) into one case row.
-- Harrington v. FB Hospitality: e00 + e04 (docket 67742498) -> keep e00
-- Slaughter v. Catholic ...:      e03 + e06 (docket 68007679) -> keep e03
-- Rule: keeper = lowest case_id per docket_id. Generic, so it also catches any other duplicates.
-- Idempotent: re-running finds no duplicates and the constraint step is guarded.
-- DRY RUN: replace the final COMMIT with ROLLBACK, and read the SELECT output first.
BEGIN;

-- 0. Preview (what will be merged)
SELECT docket_id, array_agg(case_id ORDER BY case_id) AS case_ids, count(*)
FROM litigation.cases WHERE docket_id IS NOT NULL
GROUP BY docket_id HAVING count(*) > 1;

-- 1. Map duplicates -> keeper
CREATE TEMP TABLE case_merge ON COMMIT DROP AS
SELECT case_id AS dup_id, first_value(case_id) OVER (PARTITION BY docket_id ORDER BY case_id) AS keep_id
FROM litigation.cases WHERE docket_id IS NOT NULL;
DELETE FROM case_merge WHERE dup_id = keep_id;

-- 2. Keep the keeper's claim_type unless it is NULL (fill from the duplicate)
UPDATE litigation.cases k SET claim_type = d.claim_type
FROM case_merge m JOIN litigation.cases d ON d.case_id = m.dup_id
WHERE k.case_id = m.keep_id AND k.claim_type IS NULL AND d.claim_type IS NOT NULL;

-- 3. Re-point motions (rulings and predictions hang off motions, so they follow)
UPDATE litigation.motions mo SET case_id = m.keep_id
FROM case_merge m WHERE mo.case_id = m.dup_id;

-- 4. Remove the now-empty duplicate cases
DELETE FROM litigation.cases c USING case_merge m
WHERE c.case_id = m.dup_id
  AND NOT EXISTS (SELECT 1 FROM litigation.motions mo WHERE mo.case_id = c.case_id);

-- 5. One case per docket (NULL docket_ids still allowed)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cases_docket_id_unique'
                 AND conrelid = 'litigation.cases'::regclass) THEN
    ALTER TABLE litigation.cases ADD CONSTRAINT cases_docket_id_unique UNIQUE (docket_id);
  END IF;
END $$;
COMMENT ON COLUMN litigation.cases.docket_id IS 'CourtListener docket id. Unique: one case row per lawsuit; multiple opinions = multiple motions/rulings.';
COMMENT ON TABLE litigation.cases IS 'One row per lawsuit (CourtListener docket). A lawsuit can have several motions and rulings.';

-- 6. Verify (expect 12 cases, 14 motions, 14 rulings; case_summary returns 14 rows, one per motion)
SELECT (SELECT count(*) FROM litigation.cases) AS cases,
       (SELECT count(*) FROM litigation.motions) AS motions,
       (SELECT count(*) FROM litigation.rulings) AS rulings;

COMMIT;
