from fastapi import APIRouter, HTTPException, Query

from ..legacy import Session, get_session, list_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[Session])
def read_sessions(sport: str | None = Query(default=None), city: str | None = Query(default=None)):
    sessions = list_sessions()
    if sport:
        sessions = [item for item in sessions if item.sport.lower() == sport.lower()]
    if city:
        sessions = [item for item in sessions if city.lower() in item.city.lower()]
    return sessions


@router.get("/{session_id}", response_model=Session)
def read_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/join", response_model=Session)
def join_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_joined:
        return session
    if session.joined >= session.capacity:
        session.waitlist += 1
    else:
        session.joined += 1
    session.is_joined = True
    return session


@router.post("/{session_id}/leave", response_model=Session)
def leave_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_joined:
        return session
    if session.joined >= session.capacity and session.waitlist:
        session.waitlist -= 1
    else:
        session.joined = max(0, session.joined - 1)
    session.is_joined = False
    return session
