with latest_general as (
    select max(election_date) as election_date
    from general_election
    where office = 'State Representative'
      and is_special = 0
),
active_district as (
    select distinct district_id
    from general_election, latest_general
    where office = 'State Representative'
      and is_special = 0
      and general_election.election_date = latest_general.election_date
),
latest_election as (
    select ge.district_id, max(ge.election_date) as election_date
    from general_election ge, latest_general lg
    where ge.office = 'State Representative'
      and ge.district_id in (select district_id from active_district)
      and ge.election_date >= lg.election_date
    group by ge.district_id
)
select
    ge.id_winner
from
    general_election ge
    join latest_election le
      on ge.district_id = le.district_id
     and ge.election_date = le.election_date
where
    ge.office = 'State Representative'
and ge.party_winner = 'Republican';

-- Republican State Representative incumbents with display name and years served
with latest_general as (
    select max(election_date) as election_date
    from general_election
    where office = 'State Representative'
      and is_special = 0
),
active_district as (
    select distinct district_id
    from general_election, latest_general
    where office = 'State Representative'
      and is_special = 0
      and general_election.election_date = latest_general.election_date
),
latest_election as (
    select ge.district_id, max(ge.election_date) as election_date
    from general_election ge, latest_general lg
    where ge.office = 'State Representative'
      and ge.district_id in (select district_id from active_district)
      and ge.election_date >= lg.election_date
    group by ge.district_id
),
gop_incumbent as (
    select ge.id_winner, ge.display_winner, ge.district
    from general_election ge
    join latest_election le
      on ge.district_id = le.district_id
     and ge.election_date = le.election_date
    where ge.office = 'State Representative'
      and ge.party_winner = 'Republican'
),
first_win as (
    select ge.id_winner as candidate_id, min(ge.election_date) as first_win_date
    from general_election ge
    where ge.office = 'State Representative'
      and ge.id_winner in (select id_winner from gop_incumbent)
    group by ge.id_winner
)
select
    gi.id_winner,
    gi.display_winner,
    gi.district,
    fw.first_win_date,
    cast((julianday('now') - julianday(fw.first_win_date)) / 365.25 as integer) as years_served
from gop_incumbent gi
join first_win fw on gi.id_winner = fw.candidate_id
order by years_served desc, gi.display_winner;
