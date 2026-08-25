-- How often do sitting State Reps and State Senators draw a primary
-- challenger, and how often do they lose?
--
-- Same incumbency derivation as incumbent_primary_challenges.sql, but this
-- reports rates: the denominator is every primary a sitting member ran in, so
-- a challenge rate is meaningful. Regular biennial primaries only -- specials
-- are excluded because there is no incumbent-seeking-reelection denominator.
--
-- Two thresholds are reported side by side. "any" counts a challenge if
-- anyone else appeared on the ballot, including a stray write-in; "serious"
-- requires a challenger who took at least 5% of the vote. Write-ins are not
-- filtered out, because Massachusetts primaries are winnable on a sticker
-- campaign (see incumbent_primary_challenges.sql).
--
-- Coverage caveat: 2006 and 2016 are badly under-collected upstream in
-- data/ma_primary_elections.csv.gz -- note how small incumbents_on_ballot is
-- for State Representative in those years. Read them as missing, not quiet.

WITH leg_primary AS (
    SELECT election_id,
           election_date,
           CAST(strftime('%Y', election_date) AS INTEGER) AS election_year,
           office,
           district,
           party
    FROM primary_election
    WHERE office IN ('State Representative', 'State Senate')
      AND is_special = 0
),

contender AS (
    SELECT c.*
    FROM primary_election_candidate c
    WHERE c.office IN ('State Representative', 'State Senate')
),

seat_held AS (
    SELECT office,
           district,
           id_winner     AS candidate_id,
           election_date AS won_date,
           party_winner  AS party_prev,
           LEAD(election_date) OVER (
               PARTITION BY office, district ORDER BY election_date
           ) AS next_general_date
    FROM general_election
    WHERE office IN ('State Representative', 'State Senate')
      AND id_winner IS NOT NULL
),

last_win AS (
    SELECT p.election_id,
           p.election_date,
           p.party,
           c.candidate_id,
           h.party_prev,
           h.next_general_date,
           ROW_NUMBER() OVER (
               PARTITION BY p.election_id, c.candidate_id
               ORDER BY h.won_date DESC
           ) AS win_rank
    FROM leg_primary p
    JOIN contender c ON c.election_id = p.election_id
    JOIN seat_held h
      ON h.office = p.office
     AND h.candidate_id = c.candidate_id
     AND h.won_date < p.election_date
),

-- Same-party only: a sitting member's name can be written into the other
-- party's primary without them seeking that nomination. See the note in
-- incumbent_primary_challenges.sql.
incumbent AS (
    SELECT election_id, candidate_id
    FROM last_win
    WHERE win_rank = 1
      AND (next_general_date IS NULL
           OR next_general_date > election_date)
      AND party = party_prev
),

challenger AS (
    SELECT c.election_id, c.percent
    FROM contender c
    WHERE NOT EXISTS (
        SELECT 1 FROM incumbent i
        WHERE i.election_id = c.election_id
          AND i.candidate_id = c.candidate_id
    )
),

challenger_summary AS (
    SELECT election_id,
           COUNT(*)                                         AS num_challengers,
           SUM(CASE WHEN percent >= 0.05 THEN 1 ELSE 0 END) AS num_serious
    FROM challenger
    GROUP BY election_id
),

-- One row per primary a sitting member ran in.
incumbent_primary AS (
    SELECT p.election_year,
           p.office,
           p.election_id,
           COALESCE(cs.num_challengers, 0) > 0 AS contested,
           COALESCE(cs.num_serious, 0) > 0     AS contested_serious,
           -- Did any incumbent in this contest fail to win it?
           EXISTS (
               SELECT 1 FROM incumbent i
               JOIN contender c
                 ON c.election_id = i.election_id
                AND c.candidate_id = i.candidate_id
               WHERE i.election_id = p.election_id
                 AND c.is_winner = 0
           )                                   AS incumbent_lost
    FROM leg_primary p
    JOIN (SELECT DISTINCT election_id FROM incumbent) inc
      ON inc.election_id = p.election_id
    LEFT JOIN challenger_summary cs ON cs.election_id = p.election_id
)

SELECT election_year,
       office,
       COUNT(*)                                        AS incumbents_on_ballot,
       SUM(contested)                                  AS challenged_any,
       ROUND(100.0 * SUM(contested) / COUNT(*), 1)     AS pct_challenged_any,
       SUM(contested_serious)                          AS challenged_serious,
       ROUND(100.0 * SUM(contested_serious) / COUNT(*), 1)
                                                       AS pct_challenged_serious,
       SUM(CASE WHEN contested AND incumbent_lost THEN 1 ELSE 0 END)
                                                       AS defeated,
       ROUND(100.0 * SUM(CASE WHEN contested AND incumbent_lost THEN 1 ELSE 0 END)
             / NULLIF(SUM(contested), 0), 1)           AS pct_of_challenged_lost
FROM incumbent_primary
GROUP BY election_year, office
ORDER BY election_year, office;
