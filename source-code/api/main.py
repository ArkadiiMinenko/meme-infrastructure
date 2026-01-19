from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import pika
import json
import uuid
import os
import time

app = FastAPI()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = "meme_tasks"
DB_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/memedb")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MemeTask(Base):
    __tablename__ = "memes"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="Pending")
    image_url = Column(String, nullable=True)

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

class MemeRequest(BaseModel):
    template: str
    top_text: str
    bottom_text: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/memes")
def create_task(meme: MemeRequest, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())
    
    new_task = MemeTask(task_id=task_id, status="Pending")
    db.add(new_task)
    db.commit()

    message = {
        "id": task_id,
        "template": meme.template,
        "top_text": meme.top_text,
        "bottom_text": meme.bottom_text
    }

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
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