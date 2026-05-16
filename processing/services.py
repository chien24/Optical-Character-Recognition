import logging
from typing import Dict, Any, Optional
from .models import Job
from files.models import UploadedFile

logger = logging.getLogger(__name__)


class ProcessingService:
    """Orchestrates creation and basic lifecycle of processing jobs."""

    @staticmethod
    def create_job(job_type: str, input_file: Optional[UploadedFile] = None, created_by=None, params: Dict[str, Any] = None) -> Job:
        params = params or {}
        job = Job.objects.create(
            job_type=job_type,
            input_file=input_file,
            created_by=created_by,
            params=params,
        )
        logger.info("Created job id=%s type=%s", job.id, job_type)
        return job
