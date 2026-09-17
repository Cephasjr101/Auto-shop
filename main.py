"""
Import Auto Africa — Backend API
Database: Firebase Firestore (if configured) with automatic SQLite fallback.

Run locally:   uvicorn main:app --host 0.0.0.0 --port 8000
Deploy (Render): start command -> uvicorn main:app --host 0.0.0.0 --port $PORT

Firebase setup:
  1. console.firebase.google.com -> create project -> Firestore Database (production mode)
  2. Project settings -> Service accounts -> Generate new private key (JSON)
  3. Render -> Environment -> add FIREBASE_SERVICE_ACCOUNT = <contents of that JSON, as one line>
"""
import os, time, shutil, json
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3

DB = "shop.db"
UPLOAD_DIR = "uploads"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "demo-token-123")  # change in production!

# ---------------- Firebase init (optional) ----------------
firestore_client = None
storage_bucket = None
if os.getenv("FIREBASE_SERVICE_ACCOUNT") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    try:
        from google.cloud import firestore, storage as gcs
        if os.getenv("FIREBASE_SERVICE_ACCOUNT"):
            sa = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
            firestore_client = firestore.Client.from_service_account_info(sa)
        else:
            firestore_client = firestore.Client()
        print("✅ Connected to Firebase Firestore")
        # --- Firebase Storage (photos) ---
        try:
            storage_client = gcs.Client.from_service_account_info(sa) if os.getenv("FIREBASE_SERVICE_ACCOUNT") else gcs.Client()
            bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", f"{storage_client.project}.appspot.com")
            storage_bucket = storage_client.bucket(bucket_name)
            storage_bucket.exists()  # verify reachable
            print(f"✅ Connected to Firebase Storage ({bucket_name})")
        except Exception as se:
            print(f"⚠️ Storage init failed ({se}) — uploads will save locally")
            storage_bucket = None
    except Exception as e:
        print(f"⚠️ Firebase init failed ({e}) — falling back to SQLite")

USE_FIREBASE = firestore_client is not None

app = FastAPI(title="Import Auto Africa API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------- seed data ----------------
SEED = [
    ("car","Toyota Corolla 2022 (Hybrid)",14500,"Low mileage, accident-free. Arrives Mombasa port."),
    ("car","BYD Dolphin EV 2023",16800,"Electric, 420km range, brand new from factory."),
    ("car","Toyota Hiace Van 2021",22400,"14-seater diesel — matatu/shuttle business ready."),
    ("part","Ceramic Brake Pad Set (Front)",45,"Fits Toyota/Honda/Nissan. Bulk discount from 10 sets."),
    ("part","LED Headlight Assembly Pair",120,"Plug & play, 6000K. Popular with Uber/Bolt drivers."),
    ("part","Suspension Kit (Shocks + Bushes)",150,"Tough grade for African roads. 1-year warranty."),
]

def seed_firebase():
    coll = firestore_client.collection("items")
    if len(list(coll.limit(1).stream())) == 0:
        for i, (t, n, p, d) in enumerate(SEED, start=1):
            coll.document(str(i)).set({"id": i, "type": t, "name": n, "price": p, "desc": d, "img": "", "created": int(time.time())})
        print("🌱 Seeded Firestore with sample items")

# ---------------- SQLite fallback ----------------
def sql_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite():
    conn = sql_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, name TEXT NOT NULL,
        price REAL NOT NULL, desc TEXT DEFAULT '', img TEXT DEFAULT '', created INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, customer TEXT, phone TEXT,
        note TEXT DEFAULT '', created INTEGER)""")
    if conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO items(type,name,price,desc,img,created) VALUES(?,?,?,?,?,?)",
                         [(t,n,p,d,"",int(time.time())) for t,n,p,d in SEED])
    conn.commit(); conn.close()

if USE_FIREBASE:
    seed_firebase()
else:
    init_sqlite()

# ---------------- unified data layer ----------------
def list_items():
    if USE_FIREBASE:
        return [{**d.to_dict()} for d in firestore_client.collection("items").order_by("created", direction="DESCENDING").stream()]
    conn = sql_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()]
    conn.close()
    return rows

def create_item(item):
    new_id = int(time.time())
    if USE_FIREBASE:
        firestore_client.collection("items").document(str(new_id)).set(
            {"id": new_id, "type": item.type, "name": item.name, "price": item.price,
             "desc": item.desc, "img": item.img, "created": int(time.time())})
    else:
        conn = sql_conn()
        conn.execute("INSERT INTO items(id,type,name,price,desc,img,created) VALUES(?,?,?,?,?,?,?)",
                     (new_id, item.type, item.name, item.price, item.desc, item.img, int(time.time())))
        conn.commit(); conn.close()
    return new_id

def update_item(item_id, item):
    if USE_FIREBASE:
        firestore_client.collection("items").document(str(item_id)).update(
            {"type": item.type, "name": item.name, "price": item.price, "desc": item.desc, "img": item.img})
    else:
        conn = sql_conn()
        conn.execute("UPDATE items SET type=?,name=?,price=?,desc=?,img=? WHERE id=?",
                     (item.type, item.name, item.price, item.desc, item.img, item_id))
        conn.commit(); conn.close()

def delete_item(item_id):
    if USE_FIREBASE:
        firestore_client.collection("items").document(str(item_id)).delete()
    else:
        conn = sql_conn()
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.commit(); conn.close()

def create_order(o):
    if USE_FIREBASE:
        oid = int(time.time() * 1000)
        firestore_client.collection("orders").document(str(oid)).set(
            {"id": oid, "item_name": o.item_name, "customer": o.customer, "phone": o.phone,
             "note": o.note, "created": int(time.time())})
    else:
        conn = sql_conn()
        conn.execute("INSERT INTO orders(item_name,customer,phone,note,created) VALUES(?,?,?,?,?)",
                     (o.item_name, o.customer, o.phone, o.note, int(time.time())))
        conn.commit(); conn.close()

def list_orders():
    if USE_FIREBASE:
        return [{**d.to_dict()} for d in firestore_client.collection("orders").order_by("created", direction="DESCENDING").stream()]
    conn = sql_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]
    conn.close()
    return rows

# ---------------- auth ----------------
def require_admin(authorization: str = Header(default="")):
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Invalid or missing admin token")

# ---------------- models ----------------
class ItemIn(BaseModel):
    type: str
    name: str
    price: float
    desc: str = ""
    img: str = ""

class OrderIn(BaseModel):
    item_name: str
    customer: str
    phone: str
    note: str = ""

# ---------------- public endpoints ----------------
@app.get("/api/items")
def api_list_items():
    return list_items()

@app.post("/api/orders")
def api_create_order(o: OrderIn):
    create_order(o)
    return {"ok": True}

# ---------------- admin endpoints ----------------
@app.post("/api/items")
def api_create_item(item: ItemIn, authorization: str = Header(default="")):
    require_admin(authorization)
    return {"ok": True, "id": create_item(item)}

@app.put("/api/items/{item_id}")
def api_update_item(item_id: int, item: ItemIn, authorization: str = Header(default="")):
    require_admin(authorization)
    update_item(item_id, item)
    return {"ok": True}

@app.delete("/api/items/{item_id}")
def api_delete_item(item_id: int, authorization: str = Header(default="")):
    require_admin(authorization)
    delete_item(item_id)
    return {"ok": True}

@app.get("/api/orders")
def api_list_orders(authorization: str = Header(default="")):
    require_admin(authorization)
    return list_orders()

@app.post("/api/upload")
def upload(file: UploadFile = File(...), authorization: str = Header(default="")):
    require_admin(authorization)
    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(400, "Only image files allowed")
    fname = f"{int(time.time()*1000)}{ext}"

    # Firebase Storage path (permanent, survives redeploys)
    if storage_bucket is not None:
        blob = storage_bucket.blob(f"uploads/{fname}")
        file.file.seek(0)
        blob.upload_from_file(file.file, content_type=file.content_type)
        try:
            blob.make_public()  # requires legacy ACLs on the bucket (Firebase default)
            return {"url": blob.public_url}
        except Exception:
            # fallback: signed URL valid ~10 years (workaround if ACLs unavailable)
            from datetime import timedelta
            url = blob.generate_signed_url(version="v4", expiration=timedelta(days=3650), method="GET")
            return {"url": url}

    # Local disk fallback
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file.file.seek(0)
    with open(f"{UPLOAD_DIR}/{fname}", "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/uploads/{fname}"}

# ---------------- serve frontend + uploaded images ----------------
os.makedirs(UPLOAD_DIR, exist_ok=True)
if os.path.exists("static"):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
