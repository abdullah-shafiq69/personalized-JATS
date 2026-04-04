import json

with open("results.json", "r") as f:
    final = json.load(f)

rejected  = sum(1 for r in final if r["status"] == "rejected")
interview = sum(1 for r in final if r["status"] == "interview")
pending   = sum(1 for r in final if r["status"] == "pending")
not_job   = sum(1 for r in final if r["status"] == "not_job")

print(f"\n{'='*40}")
print(f"Total classified : {len(final)}")
print(f"Rejected         : {rejected}")
print(f"Interviews       : {interview}")
print(f"Pending          : {pending}")
print(f"Not a job        : {not_job}")

print(f"{'='*40}")