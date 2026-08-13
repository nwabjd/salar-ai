# backend/app/api/knowledge_viz.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.knowledge_viz import KnowledgeVisualization

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge-viz"])


@router.get("/topics")
def topic_clusters(
    max_topics: int = 8,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    viz = KnowledgeVisualization(db)
    return viz.topic_clusters(user.id, max_topics=max_topics)
