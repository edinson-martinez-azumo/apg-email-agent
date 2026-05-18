from fastapi import APIRouter

router = APIRouter()


@router.post('/migrate')
async def run_migrations():
    """Run Alembic migrations. Call this ONCE after deployment."""
    import subprocess
    import os

    try:
        result = subprocess.run(
            ['uv', 'run', 'alembic', 'upgrade', 'head'],
            cwd=os.path.join(os.path.dirname(__file__), '..', '..'),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            return {'status': 'ok', 'message': lines[-1] if lines else 'Migrations applied'}
        else:
            return {'status': 'error', 'message': result.stderr.strip()}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
