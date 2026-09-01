#!/usr/bin/env python3
# Copyright 2026 Vyges. All Rights Reserved. Apache-2.0.
"""Regenerate pdk-catalog/index.json from the PDK mirror repos Vyges maintains.

For each PDK entry whose ``mirror`` is a dedicated ``vyges-tools`` data repo, this
refreshes ``versions[]`` / ``latest`` from that repo's git tags, recomputes the
``content_hash`` (sha256 of the descriptor), and stamps ``generated_at`` /
``generated_sha`` / ``pdk_count``.

The shared ``open_pdks`` builder is NOT used to version sky130 / gf180 — its tags
are build-system releases, not PDK release versions — so those entries stay
hand-maintained. Run by .github/workflows/update-index.yml daily.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.json")
DESCRIPTORS = os.path.join(ROOT, "descriptors")
API = "https://api.github.com"
ORG = "vyges-tools"
# Builders (not versioned PDK-data repos): their tags are not PDK versions.
SHARED_BUILDERS = {"open_pdks"}
VERSION_TAG = re.compile(r"^v?\d+(\.\d+){0,3}$|^r\d+p\d+$")


def gh(path):
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def repo_from_mirror(mirror):
    """github.com/vyges-tools/<repo> -> <repo> (only our own mirrors)."""
    if not mirror:
        return None
    m = re.match(r"github\.com/vyges-tools/([^/]+)$", mirror)
    return m.group(1) if m else None


def version_key(tag):
    core = tag[1:] if tag.startswith("v") else tag
    if re.match(r"^r\d+p\d+$", core):
        nums = re.findall(r"\d+", core)
    else:
        nums = core.split(".")
    try:
        return (0,) + tuple(int(x) for x in nums)
    except ValueError:
        return (1, tag)


def version_tags(repo):
    try:
        tags = gh("/repos/%s/%s/tags?per_page=100" % (ORG, repo))
    except urllib.error.HTTPError as e:
        print("  ! %s: tag fetch failed (HTTP %s)" % (repo, e.code), file=sys.stderr)
        return []
    names = [t["name"] for t in tags if VERSION_TAG.match(t["name"])]
    names.sort(key=version_key)
    return names


def commit_pin(desc):
    """Return ``<branch>@<sha>`` if the descriptor tracks a BRANCH rather than a release.

    A pinned entry's version index must NOT be derived from the mirror's git tags:
    ihp-open-pdk carries SG13G2 *release* tags while the tree we serve is its ``dev``
    branch, so the tags describe something other than what the descriptor points at.
    Pinned entries therefore stay hand-maintained, and the pin itself is published so
    a client can resolve the exact tree.
    """
    ref = (desc.get("upstream") or {}).get("ref") or ""
    return ref if "@" in ref else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def head_sha():
    try:
        out = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"])
        return out.decode().strip()
    except Exception:
        return None


def main():
    with open(INDEX) as f:
        idx = json.load(f)

    before = json.dumps([idx["pdks"], idx.get("pdk_count")], sort_keys=True)
    tag_cache = {}
    for entry in idx["pdks"]:
        name = entry["name"]
        descriptor = os.path.join(DESCRIPTORS, name + ".vyges-pdk.json")
        pin = None
        if os.path.exists(descriptor):
            entry["content_hash"] = sha256_file(descriptor)
            with open(descriptor) as df:
                desc = json.load(df)
            # Propagate the descriptor's serving/maturity status into the index
            # so pdk-store's quick-lookup `list` can exclude/flag it without
            # fetching each descriptor. Omit the default ("stable") to keep the
            # index minimal; a `disabled` entry stays in the index but consumers
            # must not serve it.
            st = desc.get("status", "stable")
            if st != "stable":
                entry["status"] = st
                print("  %s: status=%s" % (name, st))
            else:
                entry.pop("status", None)
            pin = commit_pin(desc)
            if pin:
                entry["pin"] = pin
            else:
                entry.pop("pin", None)

        repo = repo_from_mirror(entry.get("mirror"))
        if pin:
            print("  %s: commit-pinned %s — versions hand-maintained" % (name, pin))
        elif repo and repo not in SHARED_BUILDERS:
            if repo not in tag_cache:
                tag_cache[repo] = version_tags(repo)
            tags = tag_cache[repo]
            if tags:
                entry["versions"] = tags
                entry["latest"] = tags[-1]
                print("  %s: latest=%s (%d tag(s)) <- %s" % (name, tags[-1], len(tags), repo))
            else:
                print("  %s: no version tags on %s — keeping %s" % (name, repo, entry.get("latest")))
        else:
            print("  %s: mirror=%s — versions hand-maintained" % (name, entry.get("mirror")))

    idx["pdk_count"] = len(idx["pdks"])
    after = json.dumps([idx["pdks"], idx["pdk_count"]], sort_keys=True)
    if after == before and idx.get("generated_sha"):
        # Nothing substantive changed — leave the stamps (and the file) as-is so the
        # daily run produces no diff / no commit.
        print("no substantive change — index.json left untouched")
        return

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    idx["generated_at"] = now
    idx["generated_sha"] = head_sha()
    with open(INDEX, "w") as f:
        json.dump(idx, f, indent=2)
        f.write("\n")
    print("wrote %s (%d PDKs) @ %s" % (INDEX, idx["pdk_count"], now))


if __name__ == "__main__":
    main()
