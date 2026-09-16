"""
Import Auto Africa — Backend API
Run:  pip install -r requirements.txt
      uvicorn main:app --host 0.0.0.0 --port 8000
"""
import os, time, shutil
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3

DB = "shop.db"
UPLOAD_DIR = "uploads"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "demo-token-123")  # change in production!

app = FastAPI(title="Import Auto Africa API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- database ----------
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL, name TEXT NOT NULL,
        price REAL NOT NULL, desc TEXT DEFAULT '',
        img TEXT DEFAULT '', created INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT, customer TEXT, phone TEXT, note TEXT DEFAULT '',
        created INTEGER)""")
    if conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 0:
        seed = [
            ("car","Toyota Corolla 2022 (Hybrid)",14500,"Low mileage, accident-free. Arrives Mombasa port."),
            ("car","BYD Dolphin EV 2023",16800,"Electric, 420km range, brand new from factory."),
            ("car","Toyota Hiace Van 2021",22400,"14-seater diesel — matatu/shuttle business ready."),
            ("part","Ceramic Brake Pad Set (Front)",45,"Fits Toyota/Honda/Nissan. Bulk discount from 10 sets."),
            ("part","LED Headlight Assembly Pair",120,"Plug & play, 6000K. Popular with Uber/Bolt drivers."),
            ("part","Suspension Kit (Shocks + Bushes)",150,"Tough grade for African roads. 1-year warranty."),
        ]
        conn.executemany("INSERT INTO items(type,name,price,desc,img,created) VALUES(?,?,?,?,?,?)",
                         [(t,n,p,d,"",int(time.time())) for t,n,p,d in seed])
    conn.commit(); conn.close()

init()

# ---------- auth ----------
def require_admin(authorization: str = Header(default="")):
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Invalid or missing admin token")

# ---------- models ----------
class ItemIn(BaseModel):
    type: str          # "car" or "part"
    name: str
    price: float
    desc: str = ""
    img: str = ""      # "/uploads/xxx.jpg" or external URL

class OrderIn(BaseModel):
    item_name: str
    customer: str
    phone: str
    note: str = ""

# ---------- public endpoints ----------
@app.get("/api/items")
def list_items():
    conn = db()
    rows = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/orders")
def create_order(o: OrderIn):
    conn = db()
    conn.execute("INSERT INTO orders(item_name,customer,phone,note,created) VALUES(?,?,?,?,?)",
                 (o.item_name, o.customer, o.phone, o.note, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

# ---------- admin endpoints ----------
@app.post("/api/items")
def create_item(item: ItemIn, _: None = Header(default=None)):
    require_admin(_)
    conn = db()
    cur = conn.execute("INSERT INTO items(type,name,price,desc,img,created) VALUES(?,?,?,?,?,?)",
                 (item.type, item.name, item.price, item.desc, item.img, int(time.time())))
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return {"ok": True, "id": new_id}

@app.put("/api/items/{item_id}")
def update_item(item_id: int, item: ItemIn, _: None = Header(default=None)):
    require_admin(_)
    conn = db()
    conn.execute("UPDATE items SET type=?,name=?,price=?,desc=?,img=? WHERE id=?",
                 (item.type, item.name, item.price, item.desc, item.img, item_id))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, _: None = Header(default=None)):
    require_admin(_)
    conn = db()
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/api/orders")
def list_orders(_: None = Header(default=None)):
    require_admin(_)
    conn = db()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/upload")
def upload(file: UploadFile = File(...), _: None = Header(default=None)):
    require_admin(_)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    if ext not in (".jpg",".jpeg",".png",".webp"):
        raise HTTPException(400, "Only image files allowed")
    fname = f"{int(time.time()*1000)}{ext}"
    with open(f"{UPLOAD_DIR}/{fname}", "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/uploads/{fname}"}

# ---------- serve frontend + uploaded images ----------
if os.path.exists("static"):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
