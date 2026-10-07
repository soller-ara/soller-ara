"""One-off recovery authorized on 7 October; preserves manual run IDs and inputs."""
import datetime
import json
import os
import time
import urllib.error
import urllib.request

REPOSITORY = "soller-ara/soller-ara"
MANUAL_RUNS = (37509470872, 37512245551)
AUTO_RUNS = (37510804680, 37518022757, 37525710916, 37532989865,
             37539814209, 37545766774, 37552362829, 37556600771,
             37561458343, 37566341173, 37571052808, 37575872273)
# Keep the latest scheduled review: its checkout reads current main.
KEPT_AUTO_RUN = 37581360305


def api(path, method="GET"):
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2026-03-10"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read()
        return json.loads(content) if content else {}


def cancelable(run, jobs, expected_path):
    return (run.get("path") == expected_path and run.get("head_branch") == "main"
            and run.get("status") in {"waiting", "pending", "queued", "requested"}
            and all(not job.get("steps") and not job.get("runner_id") for job in jobs))


def cancel(run_id, expected_path):
    run = api(f"/actions/runs/{run_id}")
    jobs = api(f"/actions/runs/{run_id}/jobs").get("jobs", [])
    if not cancelable(run, jobs, expected_path):
        print(f"PRESERVE run={run_id} status={run.get('status')}", flush=True)
        return False
    api(f"/actions/runs/{run_id}/cancel", "POST")
    print(f"CANCEL_REQUESTED run={run_id}", flush=True)
    return True


def rerun(run_id):
    for _ in range(40):
        run = api(f"/actions/runs/{run_id}")
        if run.get("status") == "completed":
            if run.get("conclusion") != "cancelled":
                raise RuntimeError(f"Refusing rerun of run {run_id}: {run.get('conclusion')}")
            api(f"/actions/runs/{run_id}/rerun", "POST")
            print(f"RERUN_ACCEPTED run={run_id}; original inputs and publish key preserved", flush=True)
            return
        time.sleep(1)
    raise RuntimeError(f"Cancellation not confirmed for {run_id}")


def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise RuntimeError("Unexpected repository")
    if datetime.datetime.now(datetime.timezone.utc).date().isoformat() != "2026-10-07":
        raise RuntimeError("This one-off recovery has expired")
    canceled_manual = []
    try:
        # Cancel queued reviews and the second manual request before releasing the head.
        for run_id in AUTO_RUNS:
            cancel(run_id, ".github/workflows/update-sources.yml")
        for run_id in reversed(MANUAL_RUNS):
            if cancel(run_id, ".github/workflows/publish-own-content.yml"):
                canceled_manual.append(run_id)
    finally:
        errors = []
        for run_id in MANUAL_RUNS:
            if run_id not in canceled_manual:
                continue
            try:
                rerun(run_id)
            except Exception as error:
                errors.append(f"run={run_id}: {type(error).__name__}: {error}")
        if errors:
            raise RuntimeError("Manual reruns require attention: " + "; ".join(errors))
    print(f"RECOVERY_COMPLETE latest scheduled review retained={KEPT_AUTO_RUN}", flush=True)


if __name__ == "__main__":
    main()
