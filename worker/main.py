import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from backend.db import DB, Job, File, Artifact, now, uid
from backend import storage

logging.basicConfig(level=logging.INFO)
TIMEOUT = int(os.environ.get('JOB_TIMEOUT_SECONDS', '180'))


def claim():
    with DB.begin() as db:
        # Leases outlive subprocess limits. A dead worker's jobs fail visibly, never duplicate.
        for stale in db.scalars(select(Job).where(Job.status == 'running', Job.lease < now())):
            stale.status, stale.error = 'failed', 'Worker stopped during processing. Please retry.'
        job = db.scalar(select(Job).where(Job.status == 'queued').order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        job.status, job.lease, job.attempts = 'running', now() + timedelta(seconds=TIMEOUT + 60), job.attempts + 1
        return job.id


def run(job_id):
    with DB() as db:
        job = db.get(Job, job_id)
        file = db.get(File, job.input['file_id']) if job.input.get('file_id') else None
        payload = {'type': job.type, 'input': job.input, 'source': ''}
        with tempfile.TemporaryDirectory(prefix='lemoncad-') as temp:
            root = Path(temp)
            if file:
                if file.expires_at and file.expires_at <= now():
                    raise ValueError('Source file expired. Upload it again.')
                source = root / ('source.' + file.format)
                source.write_bytes(storage.get(file.storage_key))
                payload['source'] = str(source)
            (root / 'input.json').write_text(json.dumps(payload))
            with (root / 'process.log').open('w') as log:
                process = subprocess.Popen([sys.executable, '-m', 'worker.runner', temp], stdout=log, stderr=log, env={**os.environ, 'MPLBACKEND': 'Agg', 'OMP_NUM_THREADS': '1'})
                start = time.monotonic()
                try:
                    while process.poll() is None:
                        time.sleep(0.25)
                        db.refresh(job)
                        if job.status == 'cancelled':
                            process.kill()
                            return
                        if time.monotonic() - start > TIMEOUT:
                            raise TimeoutError('Processing exceeded three minutes. Try a smaller model.')
                    if process.returncode:
                        message = (root / 'error.txt').read_text() if (root / 'error.txt').exists() else 'CAD processing failed. Check your file and try again.'
                        raise ValueError(message)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            db.refresh(job)
            if job.status == 'cancelled':
                return
            result = json.loads((root / 'result.json').read_text())
            artifacts = result.pop('artifacts', [])
            for item in artifacts:
                path = root / item['path']
                data, key = path.read_bytes(), uid()
                storage.put(key, data)
                artifact_file = File(owner_id=job.owner_id, anonymous_session_hash=job.anonymous_session_hash, name=path.name, format=path.suffix[1:], size=len(data), sha256=hashlib.sha256(data).hexdigest(), storage_key=key, expires_at=file.expires_at if file else now() + timedelta(hours=24) if job.type == 'cad' else None)
                db.add(artifact_file)
                db.flush()
                db.add(Artifact(job_id=job.id, file_id=artifact_file.id, kind=item['kind'], revision_hash=result['revision_hash']))
                if item['kind'] == 'sheet':
                    result.setdefault('sheets', []).append(artifact_file.id)
                else:
                    result[item['kind']] = artifact_file.id
            job.result, job.status = result, 'completed'
            db.commit()


def cleanup():
    with DB.begin() as db:
        # Retain metadata for an actionable expiry error; remove expired bytes idempotently.
        for file in db.scalars(select(File).where(File.expires_at < now())):
            storage.delete(file.storage_key)


def main():
    last_cleanup = 0
    while True:
        try:
            if time.monotonic() - last_cleanup > 3600:
                cleanup()
                last_cleanup = time.monotonic()
            job_id = claim()
            if not job_id:
                time.sleep(1)
                continue
            try:
                run(job_id)
            except Exception as exc:
                logging.exception('Job %s failed', job_id)
                with DB.begin() as db:
                    job = db.get(Job, job_id)
                    if job.status != 'cancelled':
                        job.status, job.error = 'failed', str(exc)[:1500]
        except Exception:
            logging.exception('Worker loop error')
            time.sleep(5)


if __name__ == '__main__':
    main()
