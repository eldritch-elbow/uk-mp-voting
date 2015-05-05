Based on public whip open database.

MySQL hints:

CREATE user mpdata IDENTIFIED BY v0t1ng5;
GRANT ALL PRIVILEGES ON public_whip . * to mpdata;

select distinct pw_mp.mp_id from pw_vote, pw_mp where pw_vote.mp_id = pw_mp.mp_id and division_id in (select division_id from pw_division where division_date > '2010-05-06') and house='commons';





