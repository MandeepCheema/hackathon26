-- agent/duties/policy_lookup.sql
select id, topic, title, body from world.fin_policy
union all
select id, topic, title, body from world.policy_registry where status='active';
