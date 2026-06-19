import subprocess


def commit_and_push(paths: list[str], message: str, cwd: str | None = None, push: bool = True) -> bool:
    subprocess.run(["git", "add", *paths], cwd=cwd, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd)
    if staged.returncode == 0:
        return False  # nothing to commit
    subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True)
    if push:
        subprocess.run(["git", "push"], cwd=cwd, check=True)
    return True
