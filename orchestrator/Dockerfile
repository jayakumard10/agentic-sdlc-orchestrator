FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /orchestrator

# Both requirement sets: Test Executor runs pytest against target-app code
# in-process (same-language design, no compile step), so the target app's
# runtime dependencies need to be importable here too, not just the target_app
# container's own image.
COPY orchestrator/requirements.txt ./orchestrator-requirements.txt
COPY target_app/requirements.txt ./target-app-requirements.txt
RUN pip install --no-cache-dir -r orchestrator-requirements.txt -r target-app-requirements.txt

COPY orchestrator/ .

CMD ["python", "run_all_scenarios.py"]
