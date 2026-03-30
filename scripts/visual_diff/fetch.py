"""Fetch phase: mirror before/after environments locally."""

import concurrent.futures
import os
import subprocess
import sys
from pathlib import Path

from .urls import splash_url


def _is_url(s):
    return str(s).startswith(('http://', 'https://', 'file://'))


def wget_mirror(url, mirror_dir, include_path=None):
    """Mirror a URL tree using wget (depth 2, HTML only).

    include_path: if set, restrict mirroring to this directory prefix (wget -I).
    """
    mirror_dir = Path(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        'wget', '-r', '-l', '0', '-N', '-nH',
        '--force-directories', '--adjust-extension',
        '--no-check-certificate', '-q',
        '-P', str(mirror_dir),
    ]
    if include_path:
        cmd += ['-I', include_path]
    cmd.append(url)
    result = subprocess.run(cmd)
    if result.returncode not in (0, 8):
        result.check_returncode()


def _copy_local_dir(src, dst):
    """Copy a local directory to dst (rsync preferred, shutil fallback)."""
    import shutil
    src, dst = Path(src), Path(dst)
    if not src.exists():
        sys.exit(f"Error: local path does not exist: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['rsync', '-a', '--delete', f'{src}/', str(dst)])
    if r.returncode != 0:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(str(src), str(dst))


def _fetch_one(url_or_path, dest_dir, include_path=None):
    """Fetch a URL (wget) or local path (copy) into dest_dir."""
    if _is_url(str(url_or_path)):
        wget_mirror(str(url_or_path), dest_dir, include_path=include_path)
    else:
        _copy_local_dir(url_or_path, dest_dir)


def fetch_parallel(before_url, after_url, before_dir, after_dir, include_path=None):
    """Fetch both environments in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_before = pool.submit(_fetch_one, before_url, before_dir, include_path)
        f_after  = pool.submit(_fetch_one, after_url,  after_dir,  include_path)
        f_before.result()
        f_after.result()


def resolve_pr_envs(args):
    """Resolve --env-a and --env-b for PR mode."""
    env_a = args.env_a
    env_b = args.env_b

    if not env_a:
        pr_number = os.environ.get('GITHUB_EVENT_NUMBER') or os.environ.get('PR_NUMBER')
        if pr_number:
            env_a = f"titles-generated/pr-{pr_number}/"
        else:
            sys.exit("Error: --env-a is required in PR mode (or set GITHUB_EVENT_NUMBER)")

    if not env_b:
        base_ref = os.environ.get('GITHUB_BASE_REF')
        if base_ref:
            pages_base = os.environ.get('GITHUB_PAGES_BASE')
            if not pages_base:
                sys.exit("Error: --env-b is required in PR mode (or set GITHUB_BASE_REF + GITHUB_PAGES_BASE env vars)")
            env_b = f"{pages_base.rstrip('/')}/{base_ref}/"
        else:
            sys.exit("Error: --env-b is required in PR mode (or set GITHUB_BASE_REF)")

    return env_a, env_b


def resolve_before_after_urls(args):
    """Return (before_url, after_url) for the fetch phase.

    Pantheon: before=stage, after=preview
    PR:       before=env_a, after=env_b
    """
    if args.mode == 'pantheon':
        if not args.pantheon_product:
            sys.exit("Error: --pantheon-product (or $PANTHEON_PRODUCT) is required in pantheon mode")
        if not args.pantheon_version:
            sys.exit("Error: --pantheon-version (or $PANTHEON_VERSION) is required in pantheon mode")
        return (
            splash_url('stage',   args.pantheon_product, args.pantheon_version),
            splash_url('preview', args.pantheon_product, args.pantheon_version),
        )
    return resolve_pr_envs(args)
