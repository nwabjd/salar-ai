# backend/app/api/semantic_search.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.semantic_search import SemanticSearch

router = APIRouter(prefix="/api/semantic-search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

@router.post("")
def search(body: SearchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return SemanticSearch(db).search(user.id, body.query, limit=body.limit)
