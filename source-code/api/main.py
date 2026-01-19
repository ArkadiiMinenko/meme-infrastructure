from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
from dotenv import load_dotenv
import pika
import json
import uuid
import os
import time
import requests

load_dotenv('../.env')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT"))
QUEUE_NAME = "meme_tasks"

PG_USER = os.getenv("POSTGRES_USER")
PG_PASS = os.getenv("POSTGRES_PASSWORD")
PG_HOST = os.getenv("POSTGRES_HOST")
PG_DB = os.getenv("POSTGRES_DB")
DB_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:5432/{PG_DB}"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MemeTemplate(Base):
    __tablename__ = "templates"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    url = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    box_count = Column(Integer)

class MemeTask(Base):
    __tablename__ = "memes"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="Pending")
    image_url = Column(String, nullable=True)
    meta = Column(JSON, nullable=True)

def wait_for_db():
    retries = 5
    while retries > 0:
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:
            retries -= 1
            time.sleep(5)

wait_for_db()

@app.on_event("startup")
def populate_templates():
    db = SessionLocal()
    try:
        response = requests.get("https://api.imgflip.com/get_memes")
        data = response.json()
        if data['success']:
            for meme in data['data']['memes']:
                exists = db.query(MemeTemplate).filter(MemeTemplate.id == meme['id']).first()
                if not exists:
                    new_template = MemeTemplate(
                        id=meme['id'],
                        name=meme['name'],
                        url=meme['url'],
                        width=meme['width'],
                        height=meme['height'],
                        box_count=meme['box_count']
                    )
                    db.add(new_template)
            db.commit()
    except Exception as e:
        print(f"Sync Error: {e}")
    finally:
        db.close()

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "404.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=404)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)

@app.exception_handler(500)
async def global_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error. The monkeys are fixing it."}
    )

class TextLayer(BaseModel):
    text: str
    x_pos: int = 0
    y_pos: int
    size: int = 50
    color: str = "#ffffff"
    opacity: int = 100
    border_color_hex: str = "#000000"

class MemeRequest(BaseModel):
    template_id: str
    text_lines: List[TextLayer]
    text_border: bool = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/templates")
def get_templates(db: Session = Depends(get_db)):
    return db.query(MemeTemplate).all()

@app.post("/memes")
def create_task(meme: MemeRequest, db: Session = Depends(get_db)):
    template = db.query(MemeTemplate).filter(MemeTemplate.id == meme.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    task_id = str(uuid.uuid4())
    text_lines_json = [line.dict() for line in meme.text_lines]
    
    new_task = MemeTask(task_id=task_id, status="Pending", meta=text_lines_json)
    db.add(new_task)
    db.commit()

    message = {
        "id": task_id,
        "template_url": template.url,
        "text_lines": text_lines_json,
        "text_border": meme.text_border
    }

    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME)
        channel.basic_publish(exchange='', routing_key=QUEUE_NAME, body=json.dumps(message))
        connection.close()
    except Exception as e:
        db.delete(new_task)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return {"task_id": task_id, "status": "Pending"}

@app.get("/memes/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(MemeTask).filter(MemeTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task.task_id, "status": task.status, "url": task.image_url}