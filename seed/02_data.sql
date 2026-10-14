-- Small, deterministic sample dataset (so demo output is reproducible).

insert into leads (full_name, email, phone, source, status, created_at) values
    ('Amanda Cole',    'amanda.cole@example.com',    '+1-202-555-0110', 'facebook',  'closed',    now() - interval '35 days'),
    ('Brian Nguyen',   'brian.nguyen@example.com',    '+1-202-555-0111', 'referral',  'closed',    now() - interval '28 days'),
    ('Carla Diaz',     'carla.diaz@example.com',      '+1-202-555-0112', 'website',   'qualified', now() - interval '20 days'),
    ('Devon Price',    'devon.price@example.com',     '+1-202-555-0113', 'facebook',  'new',       now() - interval '5 days'),
    ('Elena Petrova',  'elena.petrova@example.com',   '+1-202-555-0114', 'facebook',  'closed',    now() - interval '12 days'),
    ('Farid Haidari',  'farid.haidari@example.com',   '+1-202-555-0115', 'referral',  'lost',      now() - interval '40 days');

insert into orders (lead_id, amount_cents, status, created_at) values
    (1, 129900, 'paid',    now() - interval '30 days'),
    (2, 49900,  'paid',    now() - interval '25 days'),
    (5, 89900,  'paid',    now() - interval '10 days');

insert into invoices (order_id, due_date, paid, notes) values
    (1, current_date - interval '5 days',  true,  'Paid via card on file'),
    (2, current_date - interval '10 days', true,  'Paid via bank transfer'),
    (3, current_date + interval '3 days',  false, 'Awaiting payment');
