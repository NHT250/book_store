# Release notes – Book Store v1.0 (Team 3)

Release 1.0 – Book Catalogue, HK261 Software Project Management final project.
Scope: F1–F5 from the Team 3 Product Backlog (16 user stories, 62 unique SP).

## Features

| Feature | Stories | What users can do |
|---|---|---|
| F1 Account management | US-01, US-02, US-11, US-19 | Register a reader account (hashed password, 8–64 characters); sign in/out with role-based landing; administrators create accounts and lock/unlock them; a locked user is signed out on the next request; an administrator cannot lock their own account |
| F2 Book management | US-09, US-21, US-22, US-23, US-14 | Add/edit books with client- and server-side validation (price > 0, cover required); soft delete (hidden, record kept); manage categories and authors; stock per shop for District 1, District 3 and Thu Duc City (CR-03 MVP) |
| F3 Book list | US-03 | Responsive grid with cover, title, author and price; newest first; 12 books per page |
| F4 Book details | US-04, US-15, US-16 | Full details with copies per shop; friendly "Book not found"; "Back to books" returns to the same page and filters |
| F5 Search / filter | US-05, US-17, US-18 | Search by title or author (case-insensitive, Vietnamese supported); filter by category and inclusive price range; all criteria kept while paging |

User interface: "bookshelf" design (responsive at desktop, tablet and phone widths).

## Quality evidence

- 67 automated tests (`python -m pytest -q`), named after the BM2 test case IDs (`test_TC_xx_yy`).
- Test case workbook BM3: 60 Pass, 4 Skipped (original CR-03 scope, not approved).
- Load time (R-06): `python scripts/benchmark_catalogue.py` – see the numbers recorded for this release in the Sprint/Final report.

## Known issues and limitations

- **CR-03 is pending a CCB decision.** Only the 3 fixed shops in the book form are built. Dynamic shop management and an "Out of stock" label on the catalogue (original CR-03 AC1, AC4) are not included.
- **Free hosting uses SQLite on an ephemeral disk.** Each redeploy or restart resets the database to the seeded demo data (32 books, 2 demo accounts); uploaded cover images are also lost. Use cover URLs for lasting demo data.
- US-17 and US-18 were completed after Sprint 3 closed (Closure, 15/11 and 17/11) and are not counted in Sprint 3 velocity.
- UAT with the customer and the hosted-URL verification are recorded separately (c5_UAT).

## How to run

```bash
pip install -r requirements.txt
python wsgi.py                 # http://127.0.0.1:5000
python -m pytest -q
python scripts/benchmark_catalogue.py
```

Demo accounts are seeded on first start: `admin@bookstore.test` (Administrator) and `customer@bookstore.test` (Customer).
Locally the passwords are the ones in README.md; on a hosted site set `DEMO_ADMIN_PASSWORD` and `DEMO_CUSTOMER_PASSWORD`.

## Deploy (free hosting)

- **Render:** New + > Blueprint > select this repository (`render.yaml`). Set `DEMO_ADMIN_PASSWORD` and `DEMO_CUSTOMER_PASSWORD`; `SECRET_KEY` is generated automatically. Health check: `/healthz`.
- **Railway / other Procfile hosts:** uses `Procfile`; set `SECRET_KEY`, `TRUST_PROXY=1`, `SESSION_COOKIE_SECURE=1` and the two demo passwords.
