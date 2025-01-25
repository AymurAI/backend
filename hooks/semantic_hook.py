from subprocess import run


def post_version(version: str):
    """
    Hook to update the version file, commit the changes, and force push the new tag.
    This hook uses the Gitmoji specification for commit messages.
    """
    # Update the version file using uv build
    run(["uv", "build", "--frozen"], check=True)

    # Commit the updated version file
    run(["git", "add", "aymurai/version.py"], check=True)
    run(["git", "commit", "-m", f"🔖 chore: update version to {version}"], check=True)
    run(["git", "push"], check=True)

    # Update and force-push the Git tag
    tag_name = f"v{version}"
    run(["git", "tag", "-f", tag_name], check=True)
    run(["git", "push", "--force", "origin", tag_name], check=True)
