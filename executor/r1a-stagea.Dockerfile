FROM python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
COPY r1a_stagea_requirements.txt /r1a-stagea-requirements.txt
RUN pip install --no-cache-dir -r /r1a-stagea-requirements.txt
COPY r1a_stagea_container.py /r1a_stagea_container.py
WORKDIR /work
USER 1001:1001
ENTRYPOINT ["python", "/r1a_stagea_container.py"]
