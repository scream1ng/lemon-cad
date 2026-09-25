"""Explicit local/admin grant; never called by the public API."""
import argparse
from datetime import timedelta
from sqlalchemy import select
from backend.db import DB, User, Entitlement, now

p=argparse.ArgumentParser();p.add_argument('email');p.add_argument('capability',choices=['costing','fixture']);p.add_argument('--days',type=int,default=30);a=p.parse_args()
with DB.begin() as db:
    user=db.scalar(select(User).where(User.email==a.email.strip().lower()))
    if not user: raise SystemExit('Account not found')
    db.add(Entitlement(user_id=user.id,capability=a.capability,grant='manual-admin',expires_at=now()+timedelta(days=a.days)))
print('Entitlement granted')
