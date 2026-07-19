from typing import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_session_factory(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    return engine, factory


def get_db(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.SessionLocal()
    try:
        yield session
    finally:
        session.close()

