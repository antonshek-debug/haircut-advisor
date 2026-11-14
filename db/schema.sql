-- haircut-advisor: tables and Row Level Security rules.
-- Run once in the Supabase SQL Editor. Safe to run again.
-- No photos, names or device IDs are stored anywhere.

-- ---------------------------------------------------------------
-- haircuts: the suggestion table (read by the page and the server)
-- ---------------------------------------------------------------
create table if not exists public.haircuts (
  id          bigint generated always as identity primary key,
  face_shape  text   not null
              check (face_shape in ('oval','round','square','oblong','heart','diamond','triangle')),
  name        text   not null,
  length      text   not null check (length in ('short','medium','long')),
  textures    text[] not null
              check (cardinality(textures) > 0
                     and textures <@ array['straight','wavy','curly','coily']),
  styles      text[] not null
              check (cardinality(styles) > 0
                     and styles <@ array['masculine','feminine','neutral']),
  reason      text   not null,  -- 1 sentence: why this cut suits the shape
  avoid       text   not null,  -- 1 sentence: what to avoid with this shape
  unique (face_shape, name)
);

-- ---------------------------------------------------------------
-- results: one anonymous row per analysed selfie
-- ---------------------------------------------------------------
create table if not exists public.results (
  id             bigint generated always as identity primary key,
  -- 6 characters made by the page; no 0, O, 1 or I
  code           text not null unique check (code ~ '^[A-HJ-NP-Z2-9]{6}$'),
  created_at     timestamptz not null default now(),

  -- the 4 measurements (PLAN.md section 5)
  length_ratio   real not null check (length_ratio   > 0 and length_ratio   < 5),   -- face length / cheekbone width
  forehead_ratio real not null check (forehead_ratio > 0 and forehead_ratio < 5),   -- forehead width / cheekbone width
  jaw_ratio      real not null check (jaw_ratio      > 0 and jaw_ratio      < 5),   -- jaw width / cheekbone width
  jaw_angle      real not null check (jaw_angle      > 0 and jaw_angle      < 180), -- degrees

  -- top 2 shapes, scores from 0 to 1
  shape_1        text not null
                 check (shape_1 in ('oval','round','square','oblong','heart','diamond','triangle')),
  score_1        real not null check (score_1 >= 0 and score_1 <= 1),
  shape_2        text not null
                 check (shape_2 in ('oval','round','square','oblong','heart','diamond','triangle')),
  score_2        real not null check (score_2 >= 0 and score_2 <= 1),

  -- the user's own choices; the page never guesses these
  length_pref    text not null check (length_pref in ('short','medium','long','any')),
  texture        text not null check (texture in ('straight','wavy','curly','coily')),
  style          text not null check (style in ('masculine','feminine','neutral'))
);

-- ---------------------------------------------------------------
-- Row Level Security
--   Phone page (anon key):    haircuts = read,  results = insert only
--   MCP server (service key): bypasses RLS, reads both tables
-- ---------------------------------------------------------------
alter table public.haircuts enable row level security;
alter table public.results  enable row level security;

-- Table privileges: start from nothing, then grant the minimum.
revoke all on public.haircuts from anon, authenticated;
revoke all on public.results  from anon, authenticated;
grant select on public.haircuts to anon;
grant insert on public.results  to anon;

drop policy if exists "anon can read haircuts" on public.haircuts;
create policy "anon can read haircuts"
  on public.haircuts for select
  to anon
  using (true);

drop policy if exists "anon can insert results" on public.results;
create policy "anon can insert results"
  on public.results for insert
  to anon
  with check (true);

-- There is no select, update or delete policy on results for anon,
-- and no select privilege either, so reading results with the anon
-- key fails with "permission denied" (test 9).
