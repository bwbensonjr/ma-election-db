-- Contested primaries for sitting State Reps and State Senators
--
-- One row per party primary in which a sitting legislator faced at least one
-- challenger from their own party. The subject is the primary: who ran, who
-- won, by what margin, in what kind of district.
--
-- Deriving incumbency
--   The primary tables carry no incumbency flag, so it is derived from
--   general_election the same way elections.R derives it: a candidate is the
--   sitting member if they won the most recent general election (regular or
--   special) for that office/district before the primary date. Matching is on
--   office + candidate rather than office + district, so a legislator whose
--   district was renumbered by redistricting is still recognized; the district
--   they last won is reported as incumbent_district_prev.
--
-- Write-ins are kept
--   Massachusetts primaries are winnable on a sticker campaign -- Kenneth
--   Gordon beat Rep. Charles Murphy in the 2012 Twenty-First Middlesex
--   Democratic primary as a write-in -- so filtering write-ins out would drop
--   real defeats. Instead every candidate counts toward the field, and
--   num_serious_challengers / challenger_percent / challenger_is_write_in let
--   you separate a real challenge from a handful of stray write-in votes.
--   For serious challenges only, add:  AND challenger_percent >= 0.05
--
-- Coverage caveat
--   State legislative primaries span 1996-2026, but the 2006 and 2016 cycles
--   are badly under-collected upstream in data/ma_primary_elections.csv.gz
--   (about 19 State Rep incumbents on the ballot in 2006 vs ~140 in most
--   cycles). Treat those two years as missing data, not quiet cycles.

WITH leg_primary AS (
    SELECT election_id,
           election_date,
           CAST(strftime('%Y', election_date) AS INTEGER) AS election_year,
           office,
           district,
           district_display,
           party,
           party_abbr,
           is_special,
           total_votes,
           blank_votes
    FROM primary_election
    WHERE office IN ('State Representative', 'State Senate')
),

contender AS (
    SELECT c.*
    FROM primary_election_candidate c
    WHERE c.office IN ('State Representative', 'State Senate')
),

field AS (
    SELECT election_id,
           COUNT(*)                                       AS num_candidates,
           SUM(CASE WHEN is_write_in = 1 THEN 1 ELSE 0 END) AS num_write_ins
    FROM contender
    GROUP BY election_id
),

-- Every general-election win, with the date of the next general held in the
-- same district. The winner is that district's most recent winner over
-- [won_date, next_general_date), which turns "most recent general before the
-- primary" into a range test.
-- prior_general_wins counts this office's wins up to and including this one.
seat_held AS (
    SELECT office,
           district,
           id_winner       AS candidate_id,
           election_date   AS won_date,
           is_special      AS won_special,
           party_winner    AS party_prev,
           LEAD(election_date) OVER (
               PARTITION BY office, district ORDER BY election_date
           )               AS next_general_date,
           COUNT(*) OVER (
               PARTITION BY office, id_winner ORDER BY election_date
           )               AS prior_general_wins,
           MIN(election_date) OVER (
               PARTITION BY office, id_winner
           )               AS first_general_win
    FROM general_election
    WHERE office IN ('State Representative', 'State Senate')
      AND id_winner IS NOT NULL
),

-- Each primary candidate paired with their most recent general-election win
-- for this office before the primary. Ranking by date matters: district names
-- are retired by redistricting (Paul Donato won Thirty-Eighth Middlesex in
-- 2000, then Thirty-Fifth Middlesex from 2002 on), and a retired district
-- never gets a next_general_date, so without this step a member's old seat
-- would look permanently unresolved and double-count them as an incumbent.
last_win AS (
    SELECT p.election_id,
           p.election_date,
           p.district,
           c.candidate_id,
           c.name,
           c.city_town,
           c.num_votes,
           c.percent,
           c.is_winner,
           h.district              AS district_prev,
           h.won_date,
           h.won_special,
           h.party_prev,
           h.next_general_date,
           h.prior_general_wins,
           h.first_general_win,
           ROW_NUMBER() OVER (
               PARTITION BY p.election_id, c.candidate_id
               ORDER BY h.won_date DESC
           ) AS win_rank
    FROM leg_primary p
    JOIN contender c
      ON c.election_id = p.election_id
    JOIN seat_held h
      ON h.office = p.office
     AND h.candidate_id = c.candidate_id
     AND h.won_date < p.election_date
),

-- A candidate is the sitting member if their most recent win has not since
-- been superseded by another general in that district. More than one
-- incumbent can appear in one contest when redistricting merges two sitting
-- members into a single district.
incumbent AS (
    SELECT election_id, candidate_id, name, city_town, num_votes, percent,
           is_winner, district_prev, won_date, won_special, party_prev,
           prior_general_wins, first_general_win,
           -- For the one-row-per-contest summary, prefer the incumbent who
           -- held this same district (mirrors elections.R).
           ROW_NUMBER() OVER (
               PARTITION BY election_id
               ORDER BY (district_prev = district) DESC, num_votes DESC
           ) AS pick
    FROM last_win
    WHERE win_rank = 1
      AND (next_general_date IS NULL
           OR next_general_date > election_date)
),

challenger AS (
    SELECT c.election_id, c.candidate_id, c.name, c.city_town, c.num_votes,
           c.percent, c.is_winner, c.is_write_in,
           ROW_NUMBER() OVER (
               PARTITION BY c.election_id ORDER BY c.num_votes DESC
           ) AS rn
    FROM contender c
    WHERE NOT EXISTS (
        SELECT 1 FROM incumbent i
        WHERE i.election_id = c.election_id
          AND i.candidate_id = c.candidate_id
    )
),

challenger_summary AS (
    SELECT election_id,
           COUNT(*)                                            AS num_challengers,
           SUM(CASE WHEN percent >= 0.05 THEN 1 ELSE 0 END)    AS num_serious_challengers
    FROM challenger
    GROUP BY election_id
),

-- Partisan lean of the district: most recent PVI vintage at or before the
-- election year. Two caveats on this join, both from district_pvi:
--
--   1. It is restricted to 2022+ because district_pvi keys every vintage to
--      post-2021 district names, so joining an older primary by district name
--      would compare different geography.
--   2. State Senate names differ between the tables -- the election tables
--      write "First Plymouth & Norfolk", district_pvi writes "First Plymouth
--      and Norfolk" -- so the join normalizes '&' to 'and'. Without this, all
--      ten multi-county Senate districts silently return no PVI.
--
-- A NULL pvi on a 2022 row is expected for 42 of the 160 State Rep districts:
-- district names in the 2008-2022 PVI vintages are mangled upstream in
-- ../mapoli/pvi/ma_state_leg_pvi_2008_2024.csv ("1Eighth Middlesex" for
-- Eighteenth, "3Fifth Middlesex" for Thirty-Fifth), so those rows cannot be
-- matched by name until the mapoli file is fixed. Only the 2024 vintage is
-- clean, which is why 2024 primaries all resolve a PVI and 2022 ones do not.
district_lean AS (
    SELECT p.election_id, v.pvi_year, v.pvi, v.pvi_n
    FROM leg_primary p
    JOIN (
        SELECT office, district, pvi_year, pvi, pvi_n,
               LEAD(pvi_year) OVER (
                   PARTITION BY office, district ORDER BY pvi_year
               ) AS next_pvi_year
        FROM district_pvi
    ) v
      ON v.office = p.office
     AND v.district = REPLACE(p.district, ' & ', ' and ')
     AND v.pvi_year <= p.election_year
     AND (v.next_pvi_year IS NULL OR v.next_pvi_year > p.election_year)
    WHERE p.election_year >= 2022
)

SELECT p.election_date,
       p.election_year,
       p.office,
       p.district,
       p.district_display,
       p.party,
       p.party_abbr,
       p.is_special,
       p.election_id,

       -- Shape of the field
       f.num_candidates,
       cs.num_challengers,
       cs.num_serious_challengers,
       f.num_write_ins,
       (SELECT COUNT(*) FROM incumbent i2
         WHERE i2.election_id = p.election_id)   AS num_incumbents,

       -- The incumbent
       i.candidate_id                            AS incumbent_id,
       i.name                                    AS incumbent,
       i.city_town                               AS incumbent_city_town,
       i.num_votes                               AS incumbent_votes,
       i.percent                                 AS incumbent_percent,
       i.is_winner                               AS incumbent_survived,
       CASE WHEN i.is_winner = 1 THEN 'survived' ELSE 'defeated' END
                                                 AS outcome,

       -- The strongest challenger, and the margin between them
       ch.candidate_id                           AS challenger_id,
       ch.name                                   AS challenger,
       ch.city_town                              AS challenger_city_town,
       ch.num_votes                              AS challenger_votes,
       ch.percent                                AS challenger_percent,
       ch.is_write_in                            AS challenger_is_write_in,
       i.percent - ch.percent                    AS margin,

       -- Turnout in the primary
       p.total_votes,
       p.blank_votes,

       -- How entrenched the incumbent was going in
       i.district_prev                           AS incumbent_district_prev,
       i.won_date                                AS incumbent_last_won,
       i.won_special                             AS incumbent_last_won_special,
       i.party_prev                              AS incumbent_party_prev,
       i.prior_general_wins,
       i.first_general_win,
       ROUND(
           (JULIANDAY(p.election_date) - JULIANDAY(i.first_general_win))
           / 365.25, 1)                          AS years_since_first_win,

       -- District partisan lean (2022+ only; see district_lean above)
       dl.pvi,
       dl.pvi_n,
       dl.pvi_year

FROM leg_primary p
JOIN field f               ON f.election_id = p.election_id
JOIN incumbent i           ON i.election_id = p.election_id AND i.pick = 1
JOIN challenger_summary cs ON cs.election_id = p.election_id
LEFT JOIN challenger ch    ON ch.election_id = p.election_id AND ch.rn = 1
LEFT JOIN district_lean dl ON dl.election_id = p.election_id

-- Contested only: at least one candidate who is not a sitting member. Drop
-- this for every primary a sitting member ran in, which is the denominator
-- for a challenge rate. Add  AND challenger_percent >= 0.05  to require a
-- challenge with real support behind it.
WHERE cs.num_challengers > 0

  -- Same-party challenges only. A sitting member's name can be written into
  -- the other party's primary without them seeking that nomination, which
  -- reads as a lopsided "defeat" -- Republican Shaunna O'Connell appears
  -- losing the 2016 Third Bristol Democratic primary on 334 write-in votes
  -- in the same cycle she won reelection as a Republican. Drop this line to
  -- see cross-party appearances too.
  AND p.party = i.party_prev

ORDER BY p.election_date DESC, p.office, p.district, p.party;
