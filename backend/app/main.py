from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import emails, drafts, auth, dashboard, products, demo, settings_api, poll
from app.api import health

app = FastAPI(
    title='APG Email Agent API',
    version='1.0.0',
    docs_url='/api/docs',
    redoc_url='/api/redoc',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.environment == 'production'
                  else [f'http://localhost:{p}' for p in range(5173, 5185)],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health.router,     prefix='/api')
app.include_router(emails.router,     prefix='/api/v1/emails',    tags=['emails'])
app.include_router(drafts.router,     prefix='/api/v1/drafts',    tags=['drafts'])
app.include_router(auth.router,       prefix='/api/v1/auth',      tags=['auth'])
app.include_router(dashboard.router,  prefix='/api/v1/dashboard', tags=['dashboard'])
app.include_router(products.router,   prefix='/api/v1/products',  tags=['products'])
app.include_router(demo.router,       prefix='/api/v1/demo',      tags=['demo'])
app.include_router(settings_api.router, prefix='/api/v1',         tags=['settings'])
app.include_router(poll.router,       prefix='/api/v1/tasks',     tags=['poll'])
