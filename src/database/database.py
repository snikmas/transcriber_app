import sqlite3

def init_db() -> None:
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS jobs (" \
        "id TEXT PRIMARY KEY UNIQUE," \
        "filename TEXT," \
        "file_path TEXT," \
        "status TEXT," \
        "source_family TEXT," \
        "is_url TEXT," \
        "download_url TEXT," \
        "created_at TIMESTAMP," \
        "result TEXT" \
        ")")

def add_job(job_id: str, job: dict | None, result: str | None) -> None:
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()
        cursor.execute('' \
        'INSERT INTO jobs (id, filename, file_path, status, source_family, is_url, download_url, created_at, result) ' \
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
        (job_id, 
         job.get('filename', None), 
         job.get('file_path', None), 
         job.get('status', None),
         job.get('source_family', None), 
         job.get('is_url', None), 
         job.get('download_url', None), 
         job.get('created_at', None),
         result))

def upload_jobs() -> list:
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM jobs')
        # utils.map_db_jobs(res)
        return cursor.fetchall() #later map it 

def update_job(job_id: str, status: str | None = None, result: str | None = None ) -> None:
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute('UPDATE jobs SET status = ? WHERE id = ?', (status, job_id))
        if result:
            cursor.execute('UPDATE jobs SET result = ? WHERE id = ?', (result, job_id))

def delete_job(job_id: str) -> None:
    with sqlite3.connect('jobs.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
