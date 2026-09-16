# Import Auto Africa — Backend

Free stack: Python + FastAPI + SQLite (no database server needed).

## 1. Install (one time)
    pip install -r requirements.txt

## 2. Run
    uvicorn main:app --host 0.0.0.0 --port 8000

- API docs (test everything in browser): http://localhost:8000/docs
- Storefront: put the frontend file in a `static/` folder next to main.py,
  then open http://localhost:8000

## 3. Admin setup
The admin token defaults to `demo-token-123`. Change it before going live:
- Linux/Mac:  export ADMIN_TOKEN="your-strong-secret"
- Windows:    set ADMIN_TOKEN=your-strong-secret
Then restart the server. The frontend will ask for this token the first time
you click "Post Item" and remember it on your device.

## 4. Image uploads
Photos you upload via the admin panel are stored in `uploads/` and served at
`/uploads/<filename>`.

## 5. Going live (~$10/month)
- Smallest VPS (Hetzner/DigitalOcean) or free tier: Render / Railway / Fly.io
- Point your domain (e.g. importautoafrica.com) at it
- Enable HTTPS (Render/Railway do this automatically; on a VPS use Caddy)
- Change ADMIN_TOKEN and remove seed data via the admin panel

## API summary
| Method | Path              | Auth  | Purpose               |
|--------|-------------------|-------|-----------------------|
| GET    | /api/items        | no    | List all listings     |
| POST   | /api/orders       | no    | Customer order capture|
| POST   | /api/items        | admin | Create listing        |
| PUT    | /api/items/{id}   | admin | Edit listing          |
| DELETE | /api/items/{id}   | admin | Delete listing        |
| POST   | /api/upload       | admin | Upload image          |
| GET    | /api/orders       | admin | View orders           |
