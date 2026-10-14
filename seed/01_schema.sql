-- Demo schema for the Guarded Postgres MCP Server.
-- Deliberately mirrors the LeadQualify demo's domain (leads -> orders -> invoices)
-- so the case-study can tell one connected story across portfolio pieces.

create table leads (
    id serial primary key,
    full_name text not null,
    email text not null,
    phone text,
    source text not null,           -- e.g. 'facebook', 'referral', 'website'
    status text not null default 'new',  -- new | qualified | closed | lost
    created_at timestamptz not null default now()
);

create table orders (
    id serial primary key,
    lead_id integer not null references leads(id),
    amount_cents integer not null,
    status text not null default 'pending',  -- pending | paid | refunded
    created_at timestamptz not null default now()
);

create table invoices (
    id serial primary key,
    order_id integer not null references orders(id),
    due_date date not null,
    paid boolean not null default false,
    notes text
);
