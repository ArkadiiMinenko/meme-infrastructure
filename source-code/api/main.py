import pika
import json
import uuid
import os
import time
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Dict
from dotenv import load_dotenv

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

TEMPLATES = {
    "doge": "https://i.imgflip.com/4t0m5.jpg",
    "disaster": "https://i.imgflip.com/23ls.jpg",
    "drake": "https://i.imgflip.com/30b1gx.jpg",
    "wonka": "https://i.imgflip.com/1bip.jpg"
}

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

class TextLayer(BaseModel):
    text: str
    y_pos: int
    size: int = 50
    color: str = "white"

class MemeRequest(BaseModel):
    template: str
    text_lines: List[TextLayer]
    text_border: bool = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/templates")
def get_templates():
    return TEMPLATES

@app.post("/memes")
def create_task(meme: MemeRequest, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())
    
    text_lines_json = [line.dict() for line in meme.text_lines]

    new_task = MemeTask(task_id=task_id, status="Pending", meta=text_lines_json)
    db.add(new_task)
    db.commit()

    message = {
        "id": task_id,
        "template": meme.template,
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